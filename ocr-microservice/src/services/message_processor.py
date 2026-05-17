"""Message processor orchestrating the complete OCR workflow."""
import asyncio
import os
import time
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime

from ..utils.logger import get_logger
from .sqs_consumer import SQSConsumer
from .s3_handler import S3Handler
from .ocr_processor import OCRProcessor
from .gedcom_uploader import GedcomUploader

if TYPE_CHECKING:
    from .openrouter_client import OpenRouterClient
    from .church_records_parser import ChurchRecordsParser
    from .gedcom_generator import GedcomGenerator

logger = get_logger(__name__)


class MessageProcessor:
    """Orchestrate the complete OCR processing workflow."""
    
    def __init__(
        self,
        config,
        logger,
        sqs_consumer: SQSConsumer,
        s3_handler: S3Handler,
        ocr_processor: OCRProcessor,
        openrouter_client: Optional['OpenRouterClient'] = None,
        church_parser: Optional['ChurchRecordsParser'] = None,
        gedcom_generator: Optional['GedcomGenerator'] = None,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
        retry_backoff_max: float = 60.0
    ):
        """
        Initialize message processor.
        
        Args:
            config: Configuration object
            logger: Logger instance
            sqs_consumer: SQS consumer instance
            s3_handler: S3 handler instance
            ocr_processor: OCR processor instance
            openrouter_client: OpenRouter client for structured data extraction (optional)
            church_parser: Church records parser (optional)
            gedcom_generator: GEDCOM generator (optional)
            max_retries: Maximum number of retry attempts
            retry_backoff_base: Base for exponential backoff (seconds)
            retry_backoff_max: Maximum backoff time (seconds)
        """
        self.config = config
        self.logger = logger
        self.sqs_consumer = sqs_consumer
        self.s3_handler = s3_handler
        self.ocr_processor = ocr_processor
        self.openrouter_client = openrouter_client
        self.church_parser = church_parser
        self.gedcom_generator = gedcom_generator
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.retry_backoff_max = retry_backoff_max
        
        # Initialize GEDCOM uploader if auto-upload is enabled
        self.gedcom_uploader: Optional[GedcomUploader] = None
        if config.ENABLE_AUTO_UPLOAD and config.HOSTED_APP_URL:
            self.gedcom_uploader = GedcomUploader(
                app_url=config.HOSTED_APP_URL,
                api_key=config.HOSTED_APP_API_KEY if config.HOSTED_APP_API_KEY else None
            )
            logger.info("GedcomUploader initialized for automatic upload")
        elif config.ENABLE_AUTO_UPLOAD and not config.HOSTED_APP_URL:
            logger.warning("ENABLE_AUTO_UPLOAD is true but HOSTED_APP_URL is not configured")
        
        logger.info("MessageProcessor initialized")
    
    def calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff time.
        
        Args:
            attempt: Current attempt number (0-indexed)
        
        Returns:
            Backoff time in seconds
        """
        backoff = min(
            self.retry_backoff_base ** attempt,
            self.retry_backoff_max
        )
        return backoff
    
    async def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single SQS message through the complete workflow.
        
        Workflow:
        1. Parse message to extract S3 URI
        2. Download image from S3
        3. Process image with OCR
        4. OpenRouter processing (if enabled)
        5. Parse church records (if OpenRouter succeeded)
        6. Generate GEDCOM (if parsing succeeded and enabled)
        7. Save markdown result locally
        8. Upload results to S3
        9. Delete SQS message
        10. Cleanup local files
        
        Args:
            message: Raw SQS message dictionary
        
        Returns:
            True if processing succeeded, False otherwise
        """
        local_image_path: Optional[str] = None
        local_result_path: Optional[str] = None
        parsed_message: Optional[Dict[str, Any]] = None
        
        try:
            # Step 1: Parse message
            logger.info(f"Processing message: {message.get('MessageId')}")
            parsed_message = self.sqs_consumer.parse_message(message)
            s3_uri = parsed_message["s3_uri"]
            receipt_handle = parsed_message["receipt_handle"]
            
            # DIAGNOSTIC: Log the exact URI format received
            logger.info(f"DIAGNOSTIC - Received S3 URI format: {s3_uri}")
            logger.info(f"DIAGNOSTIC - URI starts with 's3://': {s3_uri.startswith('s3://')}")
            logger.info(f"DIAGNOSTIC - URI starts with 'https://': {s3_uri.startswith('https://')}")
            logger.info(f"DIAGNOSTIC - URI starts with 'arn:aws:s3': {s3_uri.startswith('arn:aws:s3')}")
            
            # Step 2: Download image from S3
            # Parse S3 URI to get bucket and key
            logger.info(f"DIAGNOSTIC - About to parse S3 URI into bucket and key")
            bucket, key = self.s3_handler.parse_s3_uri(s3_uri)
            logger.info(f"DIAGNOSTIC - Successfully parsed -> bucket: '{bucket}', key: '{key}'")
            logger.info(f"DIAGNOSTIC - Bucket length: {len(bucket)}, Key length: {len(key)}")
            
            # If bucket differs from configured input bucket, log warning
            if bucket != self.s3_handler.input_bucket:
                logger.warning(
                    f"Message S3 bucket ({bucket}) differs from configured "
                    f"input bucket ({self.s3_handler.input_bucket})"
                )
            
            local_image_path = self.s3_handler.download_image(key)
            
            # Step 3: Process with OCR (run in thread to avoid event loop conflicts)
            # The datalab SDK uses asyncio.run() internally, which conflicts with our async context
            markdown_result = await asyncio.to_thread(
                self.ocr_processor.process_image,
                local_image_path
            )
            
            # Step 4: OpenRouter Processing (if enabled)
            structured_data = None
            parsed_data = None
            gedcom_content = None
            
            if self.config.ENABLE_OPENROUTER and self.openrouter_client:
                try:
                    self.logger.info("Extracting structured data with OpenRouter...")
                    structured_data = await self.openrouter_client.extract_structured_data(
                        markdown_text=markdown_result
                    )
                    self.logger.info(f"Extracted {len(structured_data.records)} records")
                    
                    # Save structured JSON if configured
                    if self.config.SAVE_INTERMEDIATE_RESULTS:
                        import json
                        structured_json = json.dumps(
                            structured_data.model_dump(),
                            indent=2,
                            ensure_ascii=False
                        )
                        self.s3_handler.upload_result(
                            content=structured_json,
                            s3_uri=s3_uri,
                            output_prefix=self.config.S3_STRUCTURED_PREFIX,
                            file_extension=".json"
                        )
                        self.logger.info("Structured data saved to S3")
                        
                except Exception as e:
                    self.logger.error(f"OpenRouter processing failed: {e}")
                    # Continue with OCR-only output
            
            # Step 5: Parse Church Records (if OpenRouter succeeded)
            if structured_data and self.church_parser:
                try:
                    self.logger.info("Parsing church records...")
                    parsed_data = self.church_parser.parse(
                        church_records=structured_data,
                        source_metadata={
                            "s3_uri": s3_uri,
                            "processing_date": datetime.now().isoformat()
                        }
                    )
                    self.logger.info(f"Parsed {len(parsed_data.persons)} individuals and {len(parsed_data.families)} families")
                except Exception as e:
                    self.logger.error(f"Church records parsing failed: {e}")
                    # Continue without GEDCOM generation
            
            # Step 6: Generate GEDCOM (if parsing succeeded and enabled)
            gedcom_uri = None
            if parsed_data and self.gedcom_generator and self.config.ENABLE_GEDCOM_GENERATION:
                try:
                    self.logger.info("Generating GEDCOM file...")
                    gedcom_content = self.gedcom_generator.generate(
                        parsed_data=parsed_data,
                        source_reference=s3_uri
                    )
                    
                    # Upload GEDCOM to S3
                    gedcom_uri = self.s3_handler.upload_result(
                        content=gedcom_content,
                        s3_uri=s3_uri,
                        output_prefix=self.config.S3_GEDCOM_PREFIX,
                        file_extension=".ged"
                    )
                    self.logger.info(f"GEDCOM file uploaded to: {gedcom_uri}")
                    
                    # Upload to hosted application if enabled
                    if self.config.ENABLE_AUTO_UPLOAD and self.gedcom_uploader and gedcom_uri:
                        try:
                            logger.info("Uploading GEDCOM to hosted application...")
                            result_basename = os.path.splitext(os.path.basename(key))[0]
                            file_id = self.gedcom_uploader.upload_gedcom(
                                gedcom_content=gedcom_content,
                                filename=f"{result_basename}.ged"
                            )
                            logger.info(f"GEDCOM uploaded and parsed on hosted app with file_id: {file_id}")
                            
                        except Exception as e:
                            logger.error(f"Failed to upload/parse on hosted app: {e}", exc_info=True)
                            # Don't fail the entire workflow if hosted app upload fails
                    
                except Exception as e:
                    self.logger.error(f"GEDCOM generation failed: {e}")
                    # Continue with other outputs
            
            # Step 7: Save markdown result locally
            result_filename = os.path.basename(local_image_path)
            result_basename = os.path.splitext(result_filename)[0]
            local_result_path = os.path.join(
                self.s3_handler.temp_dir,
                f"{result_basename}.md"
            )
            self.ocr_processor.save_result(markdown_result, local_result_path)
            
            # Step 8: Upload markdown result to S3
            result_s3_uri = self.s3_handler.upload_file_result(
                local_result_path,
                key
            )
            
            logger.info(f"OCR workflow completed successfully: {result_s3_uri}")
            
            # Step 6: Delete SQS message
            self.sqs_consumer.delete_message(receipt_handle)
            
            # Step 7: Cleanup local files
            if local_image_path:
                self.s3_handler.cleanup_local_file(local_image_path)
            if local_result_path:
                self.s3_handler.cleanup_local_file(local_result_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}", exc_info=True)
            
            # Cleanup local files on error
            if local_image_path:
                self.s3_handler.cleanup_local_file(local_image_path)
            if local_result_path:
                self.s3_handler.cleanup_local_file(local_result_path)
            
            return False
    
    async def process_message_with_retry(self, message: Dict[str, Any]) -> bool:
        """
        Process a message with retry logic and exponential backoff.
        
        Args:
            message: Raw SQS message dictionary
        
        Returns:
            True if processing succeeded (possibly after retries), False otherwise
        """
        message_id = message.get("MessageId", "unknown")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Processing attempt {attempt + 1}/{self.max_retries} "
                    f"for message {message_id}"
                )
                
                success = await self.process_message(message)
                
                if success:
                    logger.info(f"Message {message_id} processed successfully")
                    return True
                
                # If not successful and not last attempt, wait before retry
                if attempt < self.max_retries - 1:
                    backoff = self.calculate_backoff(attempt)
                    logger.warning(
                        f"Processing failed, retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(backoff)
                
            except Exception as e:
                logger.error(
                    f"Attempt {attempt + 1} failed with exception: {e}",
                    exc_info=True
                )
                
                # If not last attempt, wait before retry
                if attempt < self.max_retries - 1:
                    backoff = self.calculate_backoff(attempt)
                    logger.warning(f"Retrying in {backoff:.1f}s")
                    time.sleep(backoff)
        
        # All retries exhausted
        logger.error(
            f"Message {message_id} failed after {self.max_retries} attempts. "
            "Message will return to queue or move to DLQ."
        )
        return False
    
    async def poll_and_process(self) -> int:
        """
        Poll SQS queue once and process all received messages.
        
        Returns:
            Number of messages successfully processed
        """
        try:
            # Receive messages from SQS
            logger.info("DIAGNOSTIC - poll_and_process: About to call receive_messages()")
            messages = self.sqs_consumer.receive_messages()
            logger.info(f"DIAGNOSTIC - poll_and_process: Received {len(messages) if messages else 0} messages")
            
            if not messages:
                logger.info("DIAGNOSTIC - poll_and_process: No messages to process, returning 0")
                return 0
            
            # Process each message
            logger.info(f"DIAGNOSTIC - poll_and_process: Processing {len(messages)} message(s)")
            success_count = 0
            for idx, message in enumerate(messages):
                logger.info(f"DIAGNOSTIC - poll_and_process: Processing message {idx+1}/{len(messages)}")
                if await self.process_message_with_retry(message):
                    success_count += 1
                    logger.info(f"DIAGNOSTIC - poll_and_process: Message {idx+1} succeeded")
                else:
                    logger.error(f"DIAGNOSTIC - poll_and_process: Message {idx+1} FAILED")
            
            logger.info(
                f"Processed {success_count}/{len(messages)} messages successfully"
            )
            return success_count
            
        except Exception as e:
            logger.error(f"DIAGNOSTIC - poll_and_process: EXCEPTION CAUGHT: {e}", exc_info=True)
            return 0
