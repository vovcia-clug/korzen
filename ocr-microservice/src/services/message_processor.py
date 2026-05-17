"""Message processor orchestrating the complete OCR workflow."""
import os
import time
from typing import Optional, Dict, Any

from ..utils.logger import get_logger
from .sqs_consumer import SQSConsumer
from .s3_handler import S3Handler
from .ocr_processor import OCRProcessor

logger = get_logger(__name__)


class MessageProcessor:
    """Orchestrate the complete OCR processing workflow."""
    
    def __init__(
        self,
        sqs_consumer: SQSConsumer,
        s3_handler: S3Handler,
        ocr_processor: OCRProcessor,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
        retry_backoff_max: float = 60.0
    ):
        """
        Initialize message processor.
        
        Args:
            sqs_consumer: SQS consumer instance
            s3_handler: S3 handler instance
            ocr_processor: OCR processor instance
            max_retries: Maximum number of retry attempts
            retry_backoff_base: Base for exponential backoff (seconds)
            retry_backoff_max: Maximum backoff time (seconds)
        """
        self.sqs_consumer = sqs_consumer
        self.s3_handler = s3_handler
        self.ocr_processor = ocr_processor
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.retry_backoff_max = retry_backoff_max
        
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
    
    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single SQS message through the complete workflow.
        
        Workflow:
        1. Parse message to extract S3 URI
        2. Download image from S3
        3. Process image with OCR
        4. Save result locally
        5. Upload result to S3
        6. Delete SQS message
        7. Cleanup local files
        
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
            
            # Step 2: Download image from S3
            # Parse S3 URI to get bucket and key
            bucket, key = self.s3_handler.parse_s3_uri(s3_uri)
            
            # If bucket differs from configured input bucket, log warning
            if bucket != self.s3_handler.input_bucket:
                logger.warning(
                    f"Message S3 bucket ({bucket}) differs from configured "
                    f"input bucket ({self.s3_handler.input_bucket})"
                )
            
            local_image_path = self.s3_handler.download_image(key)
            
            # Step 3: Process with OCR
            markdown_result = self.ocr_processor.process_image(local_image_path)
            
            # Step 4: Save result locally
            result_filename = os.path.basename(local_image_path)
            result_basename = os.path.splitext(result_filename)[0]
            local_result_path = os.path.join(
                self.s3_handler.temp_dir,
                f"{result_basename}.md"
            )
            self.ocr_processor.save_result(markdown_result, local_result_path)
            
            # Step 5: Upload result to S3
            result_s3_uri = self.s3_handler.upload_result(
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
    
    def process_message_with_retry(self, message: Dict[str, Any]) -> bool:
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
                
                success = self.process_message(message)
                
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
    
    def poll_and_process(self) -> int:
        """
        Poll SQS queue once and process all received messages.
        
        Returns:
            Number of messages successfully processed
        """
        try:
            # Receive messages from SQS
            messages = self.sqs_consumer.receive_messages()
            
            if not messages:
                return 0
            
            # Process each message
            success_count = 0
            for message in messages:
                if self.process_message_with_retry(message):
                    success_count += 1
            
            logger.info(
                f"Processed {success_count}/{len(messages)} messages successfully"
            )
            return success_count
            
        except Exception as e:
            logger.error(f"Error during poll and process: {e}", exc_info=True)
            return 0
