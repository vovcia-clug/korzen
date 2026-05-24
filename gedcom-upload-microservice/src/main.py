"""Main entry point for GEDCOM Upload microservice."""
import signal
import sys
import time
from typing import Optional

from .config import Config
from .services.sqs_consumer import SQSConsumer
from .services.s3_handler import S3Handler
from .services.application_uploader import ApplicationUploader
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
    app_uploader: ApplicationUploader,
    logger
) -> bool:
    """
    Process a single GEDCOM ready message.
    
    Args:
        message: Raw SQS message
        sqs_consumer: SQS consumer instance
        s3_handler: S3 handler instance
        app_uploader: Application uploader instance
        logger: Logger instance
    
    Returns:
        True if processing succeeded, False otherwise
    """
    receipt_handle = None
    
    try:
        # Parse message
        parsed = sqs_consumer.parse_message(message)
        receipt_handle = parsed["receipt_handle"]
        message_id = parsed["message_id"]
        
        gedcom_data = parsed["gedcom_data"]
        document_metadata = parsed["document_metadata"]
        
        filename = gedcom_data.get("filename", "output.ged")
        document_id = document_metadata.get("document_id", "unknown")
        s3_uri = gedcom_data.get("s3_uri")
        gedcom_content = gedcom_data.get("content")
        
        logger.info(
            f"Processing message {message_id}: "
            f"document_id={document_id}, filename={filename}, "
            f"s3_uri={'present' if s3_uri else 'missing'}, "
            f"content={'present' if gedcom_content else 'missing'}"
        )
        
        # Check if we have S3 URI (preferred) or content
        if not s3_uri and not gedcom_content:
            logger.error(f"Message {message_id} missing both s3_uri and content")
            return False
        
        # If S3 URI is provided, use it (file already uploaded by generation service)
        if s3_uri:
            logger.info(f"GEDCOM already in S3: {s3_uri}")
            
            # Download content only if needed for application upload
            if Config.APP_UPLOAD_ENABLED and not gedcom_content:
                logger.info("Downloading GEDCOM content from S3 for application upload...")
                gedcom_content = s3_handler.download_gedcom_content(s3_uri)
        else:
            # Fallback: Upload to S3 if only content is provided (backward compatibility)
            logger.info("No S3 URI provided, uploading GEDCOM to S3...")
            s3_uri = s3_handler.upload_gedcom(
                gedcom_content=gedcom_content,
                document_id=document_id,
                filename=filename
            )
            logger.info(f"GEDCOM uploaded to S3: {s3_uri}")
        
        # Upload to application (if enabled)
        app_result = None
        if Config.APP_UPLOAD_ENABLED:
            if not gedcom_content:
                logger.warning("Cannot upload to application: no GEDCOM content available")
            else:
                logger.info("Uploading GEDCOM to hosted application...")
                app_result = app_uploader.upload_and_parse(
                    gedcom_content=gedcom_content,
                    filename=filename,
                    document_id=document_id,
                    auto_parse=Config.APP_AUTO_PARSE
                )
                
                if app_result.get("success"):
                    logger.info(f"Application upload successful: {app_result}")
                else:
                    logger.warning(f"Application upload failed: {app_result}")
                    # Don't fail the entire process if app upload fails
        else:
            logger.info("Application upload disabled, skipping")
        
        # Log final results
        logger.info(
            f"Message {message_id} processed successfully - "
            f"S3: {s3_uri}, "
            f"App: {app_result.get('success') if app_result else 'skipped'}"
        )
        
        # Delete message from queue
        sqs_consumer.delete_message(receipt_handle)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to process message: {e}", exc_info=True)
        return False


def run_with_retry(
    message: dict,
    sqs_consumer: SQSConsumer,
    s3_handler: S3Handler,
    app_uploader: ApplicationUploader,
    logger,
    max_retries: int = 3,
    retry_delay: int = 5
) -> bool:
    """
    Process message with retry logic.
    
    Args:
        message: Raw SQS message
        sqs_consumer: SQS consumer instance
        s3_handler: S3 handler instance
        app_uploader: Application uploader instance
        logger: Logger instance
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns:
        True if processing succeeded, False otherwise
    """
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Retry attempt {attempt}/{max_retries - 1}")
            time.sleep(retry_delay)
        
        success = process_message(
            message, sqs_consumer, s3_handler, app_uploader, logger
        )
        
        if success:
            return True
    
    logger.error(f"Failed to process message after {max_retries} attempts")
    return False


def main():
    """Main execution loop."""
    global shutdown_requested
    
    # Setup logging
    logger = setup_logger(__name__, level=Config.LOG_LEVEL)
    logger.info("Starting GEDCOM Upload Microservice...")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Validate configuration
        Config.validate()
        Config.log_config(logger)
        
        # Initialize AWS configuration
        aws_config = Config.get_aws_config()
        
        # Initialize SQS consumer
        sqs_consumer = SQSConsumer(
            aws_config=aws_config,
            queue_url=Config.GEDCOM_READY_QUEUE_URL,
            max_messages=Config.SQS_MAX_MESSAGES,
            wait_time_seconds=Config.SQS_WAIT_TIME_SECONDS,
            visibility_timeout=Config.SQS_VISIBILITY_TIMEOUT
        )
        
        # Initialize S3 handler
        s3_handler = S3Handler(
            aws_config=aws_config,
            output_bucket=Config.S3_OUTPUT_BUCKET,
            output_prefix=Config.S3_OUTPUT_PREFIX,
            temp_dir=Config.TEMP_DIR
        )
        
        # Initialize application uploader
        app_uploader = ApplicationUploader(
            app_url=Config.APP_URL,
            api_key=Config.APP_API_KEY,
            upload_timeout=Config.APP_UPLOAD_TIMEOUT,
            parse_timeout=Config.APP_PARSE_TIMEOUT,
            enabled=Config.APP_UPLOAD_ENABLED
        )
        
        logger.info("All services initialized successfully")
        logger.info("Starting message processing loop...")
        
        # Main processing loop
        while not shutdown_requested:
            try:
                # Poll for messages
                messages = sqs_consumer.receive_messages()
                
                if not messages:
                    continue
                
                # Process each message
                for message in messages:
                    if shutdown_requested:
                        logger.info("Shutdown requested, stopping message processing")
                        break
                    
                    run_with_retry(
                        message=message,
                        sqs_consumer=sqs_consumer,
                        s3_handler=s3_handler,
                        app_uploader=app_uploader,
                        logger=logger,
                        max_retries=Config.MAX_RETRIES,
                        retry_delay=Config.RETRY_DELAY_SECONDS
                    )
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)  # Brief pause before retrying
        
        logger.info("Shutting down gracefully...")
        logger.info(f"Waiting {Config.SHUTDOWN_GRACE_PERIOD}s for in-flight operations...")
        time.sleep(min(Config.SHUTDOWN_GRACE_PERIOD, 5))
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("GEDCOM Upload Microservice stopped")
    sys.exit(0)


if __name__ == "__main__":
    main()
