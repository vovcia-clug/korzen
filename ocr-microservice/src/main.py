"""Main entry point for OCR microservice."""
import signal
import sys
import time
from typing import Optional

from .config import Config
from .utils.logger import setup_logger, get_logger
from .services.sqs_consumer import SQSConsumer
from .services.s3_handler import S3Handler
from .services.ocr_processor import OCRProcessor
from .services.message_processor import MessageProcessor

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals (SIGTERM, SIGINT)."""
    global shutdown_requested
    logger = get_logger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def main():
    """Main application entry point."""
    global shutdown_requested
    
    # Setup logging
    logger = setup_logger(__name__, level=Config.LOG_LEVEL)
    
    logger.info("=" * 80)
    logger.info("OCR Microservice Starting")
    logger.info("=" * 80)
    
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        logger.info("Configuration validated successfully")
        logger.info(Config.display_config())
        
        # Initialize services
        logger.info("Initializing services...")
        
        # SQS Consumer
        sqs_consumer = SQSConsumer(
            aws_config=Config.get_aws_config(),
            queue_url=Config.SQS_QUEUE_URL,
            max_messages=Config.SQS_MAX_MESSAGES,
            wait_time_seconds=Config.SQS_WAIT_TIME_SECONDS,
            visibility_timeout=Config.SQS_VISIBILITY_TIMEOUT
        )
        
        # S3 Handler
        s3_handler = S3Handler(
            aws_config=Config.get_aws_config(),
            input_bucket=Config.S3_INPUT_BUCKET,
            output_bucket=Config.S3_OUTPUT_BUCKET,
            output_prefix=Config.S3_OUTPUT_PREFIX,
            temp_dir=Config.TEMP_DIR
        )
        
        # OCR Processor
        ocr_processor = OCRProcessor(
            output_format=Config.OCR_OUTPUT_FORMAT,
            mode=Config.OCR_MODE,
            paginate=Config.OCR_PAGINATE
        )
        
        # Message Processor
        message_processor = MessageProcessor(
            sqs_consumer=sqs_consumer,
            s3_handler=s3_handler,
            ocr_processor=ocr_processor,
            max_retries=Config.MAX_RETRIES,
            retry_backoff_base=Config.RETRY_BACKOFF_BASE,
            retry_backoff_max=Config.RETRY_BACKOFF_MAX
        )
        
        logger.info("All services initialized successfully")
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        logger.info("=" * 80)
        logger.info("Starting SQS polling loop (Press Ctrl+C to stop)")
        logger.info("=" * 80)
        
        # Main processing loop
        poll_count = 0
        total_processed = 0
        
        while not shutdown_requested:
            poll_count += 1
            logger.debug(f"Poll iteration {poll_count}")
            
            try:
                # Poll and process messages
                processed = message_processor.poll_and_process()
                total_processed += processed
                
                if processed > 0:
                    logger.info(
                        f"Total messages processed so far: {total_processed}"
                    )
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                # Brief sleep before continuing to avoid tight error loop
                time.sleep(5)
        
        # Graceful shutdown
        logger.info("=" * 80)
        logger.info("Shutting down gracefully...")
        logger.info(f"Total polls: {poll_count}")
        logger.info(f"Total messages processed: {total_processed}")
        logger.info("OCR Microservice stopped")
        logger.info("=" * 80)
        
        return 0
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
