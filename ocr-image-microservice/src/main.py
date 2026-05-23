"""Main entry point for OCR Image microservice."""
import sys
import time
import signal
from typing import Optional

from .config import Config
from .services.sqs_consumer import SQSConsumer
from .services.sqs_publisher import SQSPublisher
from .services.s3_handler import S3Handler
from .services.ocr_processor import OCRProcessor
from .services.metadata_extractor import MetadataExtractor
from .services.metadata_json_loader import MetadataJsonLoader
from .utils.logger import setup_logger, get_logger

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger = get_logger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def process_message(
    message: dict,
    sqs_consumer: SQSConsumer,
    s3_handler: S3Handler,
    ocr_processor: OCRProcessor,
    metadata_extractor: MetadataExtractor,
    metadata_json_loader: MetadataJsonLoader,
    sqs_publisher: SQSPublisher
) -> bool:
    """
    Process a single SQS message.
    
    Args:
        message: Raw SQS message
        sqs_consumer: SQS consumer instance
        s3_handler: S3 handler instance
        ocr_processor: OCR processor instance
        metadata_extractor: Metadata extractor instance
        metadata_json_loader: Metadata JSON loader instance
        sqs_publisher: SQS publisher instance
    
    Returns:
        True if processing succeeded, False otherwise
    """
    logger = get_logger(__name__)
    local_file_path: Optional[str] = None
    
    try:
        # Parse message
        parsed_message = sqs_consumer.parse_message(message)
        s3_uri = parsed_message["s3_uri"]
        receipt_handle = parsed_message["receipt_handle"]
        
        logger.info(f"Processing image: {s3_uri}")
        
        # Step 1: Download image from S3
        logger.info("Step 1: Downloading image from S3...")
        local_file_path = s3_handler.download_image(s3_uri)
        
        # Step 2: Load JSON metadata if available
        logger.info("Step 2: Loading JSON metadata...")
        json_metadata = metadata_json_loader.load_from_s3(s3_handler, s3_uri)
        
        # Step 3: Extract metadata from S3 path and tags
        logger.info("Step 3: Extracting metadata from S3 path and tags...")
        s3_tags = s3_handler.get_object_tags(s3_uri)
        metadata = metadata_extractor.extract_all(
            s3_uri=s3_uri,
            tags=s3_tags,
            image_path=local_file_path
        )
        
        # Step 4: Process JSON metadata if available (Skanoteka)
        if json_metadata:
            logger.info("Step 4: Processing Skanoteka metadata from JSON...")
            skanoteka_metadata = metadata_json_loader.extract_skanoteka_metadata(json_metadata)
            
            if skanoteka_metadata:
                # Merge Skanoteka metadata into main metadata
                # Skanoteka metadata takes precedence for document_id and page_number
                if 'document_id' in skanoteka_metadata:
                    metadata['document_id'] = skanoteka_metadata['document_id']
                    logger.info(f"Using document_id from Skanoteka: {skanoteka_metadata['document_id']}")
                
                if 'page_number' in skanoteka_metadata:
                    metadata['page_number'] = skanoteka_metadata['page_number']
                    logger.info(f"Using page_number from Skanoteka: {skanoteka_metadata['page_number']}")
                
                if 'total_pages' in skanoteka_metadata:
                    metadata['total_pages'] = skanoteka_metadata['total_pages']
                    logger.info(f"Using total_pages from Skanoteka: {skanoteka_metadata['total_pages']}")
                
                # Store full Skanoteka metadata for reference
                metadata['skanoteka'] = skanoteka_metadata
        else:
            logger.info("Step 4: No JSON metadata found, using extracted metadata only")
        
        logger.info(f"Final metadata: document_id={metadata.get('document_id')}, "
                   f"page_number={metadata.get('page_number')}, "
                   f"total_pages={metadata.get('total_pages')}")
        
        # Step 5: Perform OCR
        logger.info("Step 5: Performing OCR...")
        markdown_text = ocr_processor.process_image(local_file_path)
        logger.info(f"OCR completed - extracted {len(markdown_text)} characters")
        
        # Step 6: Upload OCR result to S3 (preserving directory structure)
        logger.info("Step 6: Uploading OCR result to S3...")
        ocr_result_uri = s3_handler.upload_result(
            content=markdown_text,
            s3_uri=s3_uri,
            output_prefix=Config.S3_OUTPUT_PREFIX,
            file_extension=".md",
            preserve_structure=True
        )
        logger.info(f"OCR result uploaded to: {ocr_result_uri}")
        
        # Step 7: Publish OCR result message to output queue
        logger.info("Step 7: Publishing OCR result to output queue...")
        image_dimensions = None
        if "image_width" in metadata and "image_height" in metadata:
            image_dimensions = (metadata["image_width"], metadata["image_height"])
        
        message_id = sqs_publisher.publish_ocr_result(
            source_image_uri=s3_uri,
            ocr_result_uri=ocr_result_uri,
            markdown_text=markdown_text,
            metadata=metadata,
            source_image_dimensions=image_dimensions
        )
        logger.info(f"Published OCR result message: {message_id}")
        
        # Step 8: Delete message from input queue
        logger.info("Step 8: Deleting message from input queue...")
        sqs_consumer.delete_message(receipt_handle)
        logger.info("Message deleted successfully")
        
        # Cleanup local file
        if local_file_path:
            s3_handler.cleanup_local_file(local_file_path)
        
        logger.info(f"Successfully processed image: {s3_uri}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)
        
        # Cleanup local file on error
        if local_file_path:
            s3_handler.cleanup_local_file(local_file_path)
        
        # Note: Message will become visible again after visibility timeout
        # and can be retried. For permanent failures, consider implementing
        # a dead-letter queue or error handling mechanism.
        
        return False


def main():
    """Main function to run the OCR Image microservice."""
    global shutdown_requested
    
    # Setup logging
    logger = setup_logger(__name__, level=Config.LOG_LEVEL)
    logger.info("Starting OCR Image Microservice...")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        logger.info("Configuration validated successfully")
        logger.info(Config.display_config())
        
        # Initialize AWS configuration
        aws_config = Config.get_aws_config()
        
        # Initialize services
        logger.info("Initializing services...")
        
        sqs_consumer = SQSConsumer(
            aws_config=aws_config,
            queue_url=Config.IMAGE_UPLOAD_QUEUE_URL,
            max_messages=Config.SQS_MAX_MESSAGES,
            wait_time_seconds=Config.SQS_WAIT_TIME_SECONDS,
            visibility_timeout=Config.SQS_VISIBILITY_TIMEOUT
        )
        
        sqs_publisher = SQSPublisher(
            aws_config=aws_config,
            queue_url=Config.OCR_RESULTS_QUEUE_URL
        )
        
        s3_handler = S3Handler(
            aws_config=aws_config,
            input_bucket=Config.S3_INPUT_BUCKET,
            output_bucket=Config.S3_OUTPUT_BUCKET,
            output_prefix=Config.S3_OUTPUT_PREFIX,
            temp_dir=Config.TEMP_DIR
        )
        
        ocr_processor = OCRProcessor(
            output_format=Config.OCR_OUTPUT_FORMAT,
            mode=Config.OCR_MODE,
            paginate=Config.OCR_PAGINATE
        )
        
        metadata_extractor = MetadataExtractor()
        
        metadata_json_loader = MetadataJsonLoader()
        
        logger.info("All services initialized successfully")
        logger.info("Starting message processing loop...")
        
        # Main processing loop
        while not shutdown_requested:
            try:
                # Poll for messages
                messages = sqs_consumer.receive_messages()
                
                if not messages:
                    # No messages, wait before polling again
                    logger.debug("No messages received, waiting...")
                    time.sleep(Config.POLL_INTERVAL_SECONDS)
                    continue
                
                # Process each message
                for message in messages:
                    if shutdown_requested:
                        logger.info("Shutdown requested, stopping message processing")
                        break
                    
                    success = process_message(
                        message=message,
                        sqs_consumer=sqs_consumer,
                        s3_handler=s3_handler,
                        ocr_processor=ocr_processor,
                        metadata_extractor=metadata_extractor,
                        metadata_json_loader=metadata_json_loader,
                        sqs_publisher=sqs_publisher
                    )
                    
                    if success:
                        logger.info("Message processed successfully")
                    else:
                        logger.warning("Message processing failed")
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                # Wait before retrying to avoid tight error loop
                time.sleep(Config.POLL_INTERVAL_SECONDS)
        
        logger.info("OCR Image Microservice stopped gracefully")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
