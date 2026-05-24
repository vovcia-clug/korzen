"""
Main entry point for GEDCOM Generation microservice.

This service:
1. Consumes OCR result messages from SQS
2. Groups messages by document_id
3. Waits for document completion (all pages or timeout)
4. Formats document with metadata
5. Generates GEDCOM via LLM
6. Validates GEDCOM
7. Uploads to S3
8. Publishes GEDCOM ready message
"""

import asyncio
import signal
import sys
import time
from typing import Optional

from .config import Config
from .services.sqs_consumer import SQSConsumer
from .services.sqs_publisher import SQSPublisher
from .services.s3_handler import S3Handler
from .services.openrouter_client import OpenRouterClient
from .services.document_grouper import DocumentGrouper
from .services.gedcom_generator import GedcomGenerator
from .services.gedcom_validator import GedcomValidator
from .utils.logger import setup_logger, get_logger
from .utils import langfuse_tracer

# Initialize logger
logger = setup_logger(__name__, level=Config.LOG_LEVEL)


class GedcomGenerationService:
    """Main service class for GEDCOM generation."""
    
    def __init__(self):
        """Initialize the service with all components."""
        logger.info("Initializing GEDCOM Generation Service...")
        
        # Validate configuration
        try:
            Config.validate()
            logger.info("Configuration validated successfully")
            logger.info(f"Configuration: {Config.to_dict()}")
        except ValueError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise
        
        # Initialize AWS clients
        aws_config = Config.get_aws_config()
        
        # SQS Consumer (input: OCR results)
        self.sqs_consumer = SQSConsumer(
            aws_config=aws_config,
            queue_url=Config.OCR_RESULTS_QUEUE_URL,
            max_messages=Config.SQS_MAX_MESSAGES,
            wait_time_seconds=Config.SQS_WAIT_TIME_SECONDS,
            visibility_timeout=Config.SQS_VISIBILITY_TIMEOUT
        )
        
        # SQS Publisher (output: GEDCOM ready)
        self.sqs_publisher = SQSPublisher(
            aws_config=aws_config,
            queue_url=Config.GEDCOM_READY_QUEUE_URL
        )
        
        # S3 Handler (upload GEDCOM files)
        self.s3_handler = S3Handler(
            aws_config=aws_config,
            output_bucket=Config.S3_OUTPUT_BUCKET,
            output_prefix=Config.S3_GEDCOM_PREFIX
        )
        
        # OpenRouter Client
        self.openrouter_client = OpenRouterClient(
            api_key=Config.OPENROUTER_API_KEY,
            model=Config.OPENROUTER_MODEL,
            base_url=Config.OPENROUTER_BASE_URL,
            timeout=Config.OPENROUTER_TIMEOUT,
            max_retries=Config.MAX_RETRIES,
            retry_backoff_base=Config.RETRY_BACKOFF_BASE,
            retry_backoff_max=Config.RETRY_BACKOFF_MAX
        )
        
        # Document Grouper
        self.document_grouper = DocumentGrouper(
            timeout_seconds=Config.GROUPING_TIMEOUT_SECONDS,
            use_redis=Config.USE_REDIS,
            redis_host=Config.REDIS_HOST,
            redis_port=Config.REDIS_PORT,
            redis_db=Config.REDIS_DB,
            redis_key_prefix=Config.REDIS_KEY_PREFIX
        )
        
        # GEDCOM Generator
        self.gedcom_generator = GedcomGenerator(
            openrouter_client=self.openrouter_client,
            gedcom_version=Config.GEDCOM_VERSION
        )
        
        # GEDCOM Validator
        self.gedcom_validator = GedcomValidator(
            strict=Config.STRICT_VALIDATION
        )
        
        # Service state
        self.running = False
        self.last_timeout_check = time.time()
        
        logger.info("GEDCOM Generation Service initialized successfully")
    
    async def process_message(self, message: dict) -> None:
        """
        Process a single OCR result message.
        
        Args:
            message: Raw SQS message
        """
        # Parse message first to get document_id for tracing
        parsed = self.sqs_consumer.parse_message(message)
        document_id = parsed["metadata"].get("document_id", "unknown")
        message_id = parsed.get("message_id", "unknown")
        
        try:
            # Check if already processed (idempotency)
            if self.document_grouper.is_already_processed(document_id):
                logger.info(f"Document {document_id} already processed. Skipping.")
                self.sqs_consumer.delete_message(parsed["receipt_handle"])
                return
            
            # Add to document group (automatically traced by @observe decorator)
            self.document_grouper.add_message(parsed)
            
            # Check if document is complete
            is_complete, reason = self.document_grouper.is_complete(document_id)
            
            if is_complete:
                logger.info(
                    f"Document {document_id} is complete (reason: {reason}). "
                    f"Processing..."
                )
                await self.process_complete_document(document_id, reason)
                # Mark as processed AFTER successful processing
                self.document_grouper.mark_as_processed(document_id)
                # Delete message ONLY after successful processing
                self.sqs_consumer.delete_message(parsed["receipt_handle"])
            else:
                # Get detailed state for debugging
                group = self.document_grouper.get_group(document_id)
                if group:
                    page_numbers = sorted([
                        m.get("metadata", {}).get("page_number")
                        for m in group.messages
                        if m.get("metadata", {}).get("page_number") is not None
                    ])
                    logger.info(
                        f"Document {document_id} is incomplete. "
                        f"Received: {len(group.messages)} messages, "
                        f"Expected: {group.expected_pages or 'unknown'}, "
                        f"Pages: {page_numbers}, "
                        f"Waiting for more pages..."
                    )
                else:
                    logger.info(
                        f"Document {document_id} is incomplete. "
                        f"Waiting for more pages..."
                    )
                # Delete incomplete messages immediately (they're buffered in memory)
                self.sqs_consumer.delete_message(parsed["receipt_handle"])
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            # Don't delete message - it will become visible again for retry
    
    @langfuse_tracer.observe(name="process-document-group")
    async def process_complete_document(
        self,
        document_id: str,
        completion_reason: str
    ) -> None:
        """
        Process a complete document group.
        
        Args:
            document_id: Document identifier
            completion_reason: Reason for completion (all_pages_received, timeout_reached)
        """
        try:
            # Get document group
            group = self.document_grouper.get_group(document_id)
            if not group:
                error_msg = f"Document group not found: {document_id}"
                logger.error(error_msg)
                langfuse_tracer.log_error(
                    ValueError(error_msg),
                    context={
                        "document_id": document_id,
                        "operation": "get_document_group"
                    }
                )
                return
            
            # Get sorted messages
            sorted_messages = group.get_sorted_messages()
            document_metadata = group.metadata
            
            # Create span for document group processing with metadata
            page_numbers = group.get_page_numbers()
            valid_page_numbers = [p for p in page_numbers if p is not None]
            
            group_metadata = {
                "document_id": document_id,
                "num_pages": len(sorted_messages),
                "expected_pages": group.expected_pages,
                "completion_reason": completion_reason,
                "document_title": document_metadata.get("document_title", ""),
                "location": document_metadata.get("location", ""),
                "date_range": document_metadata.get("date_range", ""),
                "page_numbers_received": valid_page_numbers
            }
            
            with langfuse_tracer.create_span(
                name="process-document-group",
                metadata=group_metadata
            ):
                logger.info(
                    f"Processing document {document_id}: "
                    f"{len(sorted_messages)} pages, "
                    f"completion: {completion_reason}"
                )
                
                # Check for missing pages
                if group.expected_pages:
                    if valid_page_numbers:
                        expected = set(range(1, group.expected_pages + 1))
                        received = set(valid_page_numbers)
                        missing = expected - received
                        if missing:
                            logger.warning(
                                f"Document {document_id} has missing pages: {sorted(missing)}"
                            )
                            # Log warning to Langfuse
                            langfuse_tracer.log_error(
                                ValueError(f"Missing pages: {sorted(missing)}"),
                                context={
                                    "document_id": document_id,
                                    "operation": "page_completeness_check",
                                    "missing_pages": sorted(missing),
                                    "expected_pages": group.expected_pages,
                                    "received_pages": sorted(received)
                                },
                                level="WARNING"
                            )
                    else:
                        logger.warning(
                            f"Document {document_id} has no valid page numbers, "
                            f"cannot verify completeness"
                        )
                
                # Generate GEDCOM (automatically traced by @observe decorator)
                start_time = time.time()
                try:
                    gedcom_content = await self.gedcom_generator.generate_from_document_group(
                        sorted_messages,
                        document_metadata
                    )
                    generation_time = time.time() - start_time
                except Exception as e:
                    logger.error(f"GEDCOM generation failed for {document_id}: {e}")
                    langfuse_tracer.log_error(
                        e,
                        context={
                            "document_id": document_id,
                            "operation": "gedcom_generation",
                            "num_pages": len(sorted_messages)
                        }
                    )
                    raise
                
                # Count records
                record_counts = self.gedcom_generator.count_gedcom_records(gedcom_content)
                
                # Add Langfuse score metrics for tracking all entity types
                langfuse_tracer.add_score(
                    name="total_persons",
                    value=record_counts["total_persons"],
                    comment=f"Total persons (individuals) in document {document_id}"
                )
                langfuse_tracer.add_score(
                    name="individuals_processed",
                    value=record_counts["individuals"],
                    comment=f"Number of individuals processed in document {document_id}"
                )
                langfuse_tracer.add_score(
                    name="families_processed",
                    value=record_counts["families"],
                    comment=f"Number of families processed in document {document_id}"
                )
                langfuse_tracer.add_score(
                    name="baptisms_processed",
                    value=record_counts["baptisms"],
                    comment=f"Number of baptisms processed in document {document_id}"
                )
                langfuse_tracer.add_score(
                    name="deaths_processed",
                    value=record_counts["deaths"],
                    comment=f"Number of deaths processed in document {document_id}"
                )
                langfuse_tracer.add_score(
                    name="marriages_processed",
                    value=record_counts["marriages"],
                    comment=f"Number of marriages processed in document {document_id}"
                )
                langfuse_tracer.add_score(
                    name="total_events",
                    value=record_counts["total_events"],
                    comment=f"Total events (baptisms + deaths + marriages) in document {document_id}"
                )
                
                # Validate GEDCOM
                validation_status = "valid"
                if Config.ENABLE_GEDCOM_VALIDATION:
                    try:
                        is_valid, errors = await self._validate_gedcom(gedcom_content)
                        validation_status = "valid" if is_valid else "invalid"
                        
                        if not is_valid:
                            logger.warning(
                                f"GEDCOM validation failed for {document_id}: "
                                f"{len(errors)} error(s)"
                            )
                            for error in errors[:5]:
                                logger.warning(f"  - {error}")
                            
                            # Log validation errors to Langfuse
                            langfuse_tracer.log_error(
                                ValueError(f"GEDCOM validation failed: {len(errors)} errors"),
                                context={
                                    "document_id": document_id,
                                    "operation": "gedcom_validation",
                                    "error_count": len(errors),
                                    "sample_errors": errors[:5]
                                },
                                level="WARNING"
                            )
                    except Exception as e:
                        logger.error(f"GEDCOM validation error for {document_id}: {e}")
                        langfuse_tracer.log_error(
                            e,
                            context={
                                "document_id": document_id,
                                "operation": "gedcom_validation"
                            }
                        )
                        # Continue processing even if validation fails
                
                # Upload to S3 (preserve directory structure from first source image)
                try:
                    # Get the first source image URI to preserve directory structure
                    source_image_uri = None
                    if sorted_messages:
                        source_image_uri = sorted_messages[0].get("source_image", {}).get("s3_uri")
                    
                    s3_uri = await self._upload_to_s3(
                        document_id,
                        gedcom_content,
                        source_image_uri=source_image_uri
                    )
                except Exception as e:
                    logger.error(f"S3 upload failed for {document_id}: {e}")
                    langfuse_tracer.log_error(
                        e,
                        context={
                            "document_id": document_id,
                            "operation": "s3_upload",
                            "gedcom_size_bytes": len(gedcom_content)
                        }
                    )
                    raise
                
                # Prepare GEDCOM ready message
                gedcom_ready_message = {
                    "document_metadata": {
                        "document_id": document_id,
                        "document_title": document_metadata.get("document_title", ""),
                        "date_range": document_metadata.get("date_range", ""),
                        "location": document_metadata.get("location", ""),
                        "total_pages": group.expected_pages or len(sorted_messages),
                        "pages_processed": len(sorted_messages),
                        "completion_reason": completion_reason
                    },
                    "gedcom_data": {
                        "content": gedcom_content,
                        "filename": f"{document_id}.ged",
                        "s3_uri": s3_uri,
                        "validation_status": validation_status,
                        "individual_count": record_counts["individuals"],
                        "family_count": record_counts["families"],
                        "baptism_count": record_counts["baptisms"],
                        "death_count": record_counts["deaths"],
                        "marriage_count": record_counts["marriages"],
                        "total_events": record_counts["total_events"]
                    },
                    "source_ocr_uris": [
                        msg.get("ocr_result", {}).get("s3_uri", "")
                        for msg in sorted_messages
                    ],
                    "metadata": {
                        "processing_time_ms": int(generation_time * 1000),
                        "openrouter_model": Config.OPENROUTER_MODEL
                    }
                }
                
                # Publish GEDCOM ready message
                try:
                    await self._publish_to_sqs(gedcom_ready_message)
                except Exception as e:
                    logger.error(f"SQS publish failed for {document_id}: {e}")
                    langfuse_tracer.log_error(
                        e,
                        context={
                            "document_id": document_id,
                            "operation": "sqs_publish"
                        }
                    )
                    raise
                
                # Remove document group
                self.document_grouper.remove_group(document_id)
                
                logger.info(
                    f"Successfully processed document {document_id}: "
                    f"{record_counts['individuals']} individuals, "
                    f"{record_counts['families']} families, "
                    f"{record_counts['baptisms']} baptisms, "
                    f"{record_counts['deaths']} deaths, "
                    f"{record_counts['marriages']} marriages, "
                    f"validation: {validation_status}"
                )
            
        except Exception as e:
            logger.error(
                f"Error processing complete document {document_id}: {e}",
                exc_info=True
            )
            # Log the top-level error to Langfuse
            langfuse_tracer.log_error(
                e,
                context={
                    "document_id": document_id,
                    "operation": "process_complete_document",
                    "completion_reason": completion_reason
                }
            )
            # Don't remove group - allow retry
    
    async def _validate_gedcom(self, gedcom_content: str) -> tuple[bool, list]:
        """
        Validate GEDCOM content.
        
        Args:
            gedcom_content: GEDCOM file content
            
        Returns:
            Tuple of (is_valid, errors)
        """
        is_valid, errors = self.gedcom_validator.validate(gedcom_content)
        return is_valid, errors
    
    async def _upload_to_s3(
        self,
        document_id: str,
        gedcom_content: str,
        source_image_uri: Optional[str] = None
    ) -> str:
        """
        Upload GEDCOM to S3.
        
        Args:
            document_id: Document identifier
            gedcom_content: GEDCOM file content
            source_image_uri: Optional source image URI to preserve directory structure
            
        Returns:
            S3 URI of uploaded file
        """
        filename = f"{document_id}.ged"
        s3_uri = self.s3_handler.upload_gedcom(
            content=gedcom_content,
            document_id=document_id,
            filename=filename,
            source_s3_uri=source_image_uri,
            preserve_structure=True
        )
        return s3_uri
    
    async def _publish_to_sqs(self, gedcom_ready_message: dict) -> None:
        """
        Publish GEDCOM ready message to SQS.
        
        Args:
            gedcom_ready_message: Message to publish
        """
        self.sqs_publisher.publish_gedcom_ready(
            document_metadata=gedcom_ready_message["document_metadata"],
            gedcom_data=gedcom_ready_message["gedcom_data"],
            source_ocr_uris=gedcom_ready_message["source_ocr_uris"],
            processing_metadata=gedcom_ready_message["metadata"]
        )
    
    async def check_timeouts(self) -> None:
        """Check for timed-out documents and process them."""
        try:
            timed_out = self.document_grouper.check_timeouts()
            
            for document_id in timed_out:
                logger.info(f"Processing timed-out document: {document_id}")
                await self.process_complete_document(document_id, "timeout_reached")
                
        except Exception as e:
            logger.error(f"Error checking timeouts: {e}", exc_info=True)
    
    async def run(self) -> None:
        """Main service loop."""
        self.running = True
        logger.info("Starting GEDCOM Generation Service main loop...")
        
        while self.running:
            try:
                # Receive messages from SQS
                messages = self.sqs_consumer.receive_messages()
                
                # Process each message
                for message in messages:
                    await self.process_message(message)
                
                # Periodically check for timeouts
                if time.time() - self.last_timeout_check > Config.GROUPING_CHECK_INTERVAL:
                    await self.check_timeouts()
                    self.last_timeout_check = time.time()
                
                # Brief sleep if no messages
                if not messages:
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, shutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying
        
        logger.info("GEDCOM Generation Service stopped")
    
    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down GEDCOM Generation Service...")
        self.running = False
        
        # Close OpenRouter client
        await self.openrouter_client.close()
        
        # Flush Langfuse traces
        langfuse_tracer.flush()
        
        logger.info("Shutdown complete")


async def main():
    """Main entry point."""
    service = None
    
    try:
        # Create service
        service = GedcomGenerationService()
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            if service:
                asyncio.create_task(service.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run service
        await service.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if service:
            await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
