"""Main entry point for OCR microservice."""
import asyncio
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
from .services.openrouter_client import OpenRouterClient
from .services.church_records_parser import ChurchRecordsParser
from .services.gedcom_generator import GedcomGenerator

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals (SIGTERM, SIGINT)."""
    global shutdown_requested
    logger = get_logger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


async def main():
    """Main application entry point."""
    global shutdown_requested
    
    # Setup logging for main module
    logger = setup_logger(__name__, level=Config.LOG_LEVEL)
    
    # DIAGNOSTIC: Setup logging for all child modules to ensure their logs show
    setup_logger("src.services.sqs_consumer", level=Config.LOG_LEVEL)
    setup_logger("src.services.message_processor", level=Config.LOG_LEVEL)
    setup_logger("src.services.s3_handler", level=Config.LOG_LEVEL)
    setup_logger("src.services.ocr_processor", level=Config.LOG_LEVEL)
    setup_logger("src.config", level=Config.LOG_LEVEL)
    
    # Create config instance
    config = Config()
    
    logger.info("=" * 80)
    logger.info("OCR Microservice Starting")
    logger.info("=" * 80)
    
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        config.validate()
        logger.info("Configuration validated successfully")
        logger.info(config.display_config())
        
        # Initialize services
        logger.info("Initializing services...")
        
        # SQS Consumer
        sqs_consumer = SQSConsumer(
            aws_config=config.get_aws_config(),
            queue_url=config.SQS_QUEUE_URL,
            max_messages=config.SQS_MAX_MESSAGES,
            wait_time_seconds=config.SQS_WAIT_TIME_SECONDS,
            visibility_timeout=config.SQS_VISIBILITY_TIMEOUT
        )
        
        # S3 Handler
        s3_handler = S3Handler(
            aws_config=config.get_aws_config(),
            input_bucket=config.S3_INPUT_BUCKET,
            output_bucket=config.S3_OUTPUT_BUCKET,
            output_prefix=config.S3_OUTPUT_PREFIX,
            temp_dir=config.TEMP_DIR
        )
        
        # OCR Processor
        ocr_processor = OCRProcessor(
            output_format=config.OCR_OUTPUT_FORMAT,
            mode=config.OCR_MODE,
            paginate=config.OCR_PAGINATE
        )
        
        # Initialize new services for GEDCOM processing
        openrouter_client = None
        church_parser = None
        gedcom_generator = None
        
        if config.ENABLE_OPENROUTER:
            if not config.OPENROUTER_API_KEY:
                logger.warning("OpenRouter enabled but OPENROUTER_API_KEY not set. Skipping OpenRouter processing.")
            else:
                logger.info("Initializing OpenRouter client...")
                openrouter_client = OpenRouterClient(config=config, logger=logger)
                
                logger.info("Initializing church records parser...")
                church_parser = ChurchRecordsParser(logger=logger)
                
                if config.ENABLE_GEDCOM_GENERATION:
                    logger.info("Initializing GEDCOM generator...")
                    gedcom_generator = GedcomGenerator(logger=logger)
        else:
            logger.info("OpenRouter processing disabled. OCR-only mode active.")
        
        # Message Processor
        message_processor = MessageProcessor(
            config=config,
            logger=logger,
            sqs_consumer=sqs_consumer,
            s3_handler=s3_handler,
            ocr_processor=ocr_processor,
            openrouter_client=openrouter_client,
            church_parser=church_parser,
            gedcom_generator=gedcom_generator,
            max_retries=config.MAX_RETRIES,
            retry_backoff_base=config.RETRY_BACKOFF_BASE,
            retry_backoff_max=config.RETRY_BACKOFF_MAX
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
            logger.info(f"DIAGNOSTIC - Poll iteration {poll_count} starting...")
            
            try:
                # Poll and process messages
                logger.info("DIAGNOSTIC - About to call poll_and_process()")
                processed = await message_processor.poll_and_process()
                logger.info(f"DIAGNOSTIC - poll_and_process() returned: {processed}")
                total_processed += processed
                
                if processed > 0:
                    logger.info(
                        f"Total messages processed so far: {total_processed}"
                    )
                else:
                    logger.info("DIAGNOSTIC - No messages were processed in this iteration")
                
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
    sys.exit(asyncio.run(main()))
