"""
Main entry point for GEDCOM Generation microservice.

This service:
1. Consumes OCR result messages from SQS (continuous background poller)
2. Routes each page to a per-document asyncio.Queue
3. Spawns a PageProcessorTask per document that processes pages sequentially
   (preserving rolling context extraction) while the poller keeps running
4. Validates GEDCOM, uploads to S3, publishes GEDCOM-ready message per page
5. Handles document completion (all pages received or timeout)

Pipeline parallelism: SQS polling and GEDCOM generation run concurrently.
Pages are processed as they arrive — no waiting for the full document.
"""

import asyncio
import signal
import sys
import time
from typing import Optional, Dict

from .config import Config
from .services.sqs_consumer import SQSConsumer
from .services.sqs_publisher import SQSPublisher
from .services.s3_handler import S3Handler
from .services.openrouter_client import OpenRouterClient
from .services.document_grouper import DocumentGrouper
from .services.gedcom_generator import GedcomGenerator
from .services.context_extractor import ContextExtractor
from .services.gedcom_validator import GedcomValidator
from .utils.logger import setup_logger, get_logger
from .utils import langfuse_tracer

# Initialize logger
logger = setup_logger(__name__, level=Config.LOG_LEVEL)

# Sentinel value placed on a per-document queue to signal the
# PageProcessorTask that no more pages will arrive (timeout or shutdown).
_QUEUE_SENTINEL = None


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
            visibility_timeout=Config.SQS_VISIBILITY_TIMEOUT,
        )

        # SQS Publisher (output: GEDCOM ready)
        self.sqs_publisher = SQSPublisher(
            aws_config=aws_config,
            queue_url=Config.GEDCOM_READY_QUEUE_URL,
        )

        # S3 Handler (upload GEDCOM files)
        self.s3_handler = S3Handler(
            aws_config=aws_config,
            output_bucket=Config.S3_OUTPUT_BUCKET,
            output_prefix=Config.S3_GEDCOM_PREFIX,
        )

        # OpenRouter Client
        self.openrouter_client = OpenRouterClient(
            api_key=Config.OPENROUTER_API_KEY,
            model=Config.OPENROUTER_MODEL,
            base_url=Config.OPENROUTER_BASE_URL,
            timeout=Config.OPENROUTER_TIMEOUT,
            max_retries=Config.MAX_RETRIES,
            retry_backoff_base=Config.RETRY_BACKOFF_BASE,
            retry_backoff_max=Config.RETRY_BACKOFF_MAX,
        )

        # Document Grouper
        self.document_grouper = DocumentGrouper(
            timeout_seconds=Config.GROUPING_TIMEOUT_SECONDS,
        )

        # Context Extractor (carry-forward document-level context between pages)
        # Context extraction is always enabled
        self.context_extractor = ContextExtractor(
            openrouter_client=self.openrouter_client,
            max_context_chars=Config.MAX_CONTEXT_CHARS,
        )

        # GEDCOM Generator
        self.gedcom_generator = GedcomGenerator(
            openrouter_client=self.openrouter_client,
            gedcom_version=Config.GEDCOM_VERSION,
            context_extractor=self.context_extractor,
        )

        # GEDCOM Validator
        self.gedcom_validator = GedcomValidator(
            strict=Config.STRICT_VALIDATION,
        )

        # ----------------------------------------------------------------
        # Pipeline-parallelism state
        # ----------------------------------------------------------------
        # Per-document rolling LLM context (document_id → context string).
        # Protected by _state_lock because the poller task and processor
        # tasks run concurrently.
        self._rolling_contexts: Dict[str, str] = {}

        # Per-document 1-based page-index counter (document_id → int).
        # Incremented by the poller each time a new page arrives so that
        # generate_single_page() receives a stable, monotonically increasing
        # index even when pages arrive out of order.
        self._page_indices: Dict[str, int] = {}

        # Asyncio lock protecting _rolling_contexts and _page_indices.
        self._state_lock: asyncio.Lock = asyncio.Lock()

        # Service state
        self.running = False

        logger.info("GEDCOM Generation Service initialized successfully")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Main service loop.

        Runs two concurrent background tasks:
        - SQS poller: continuously polls for new messages and routes each
          page to the appropriate per-document queue.
        - Timeout checker: periodically checks for documents that have not
          received all pages within GROUPING_TIMEOUT_SECONDS and signals
          their processor tasks to flush and finish.
        """
        self.running = True
        logger.info("Starting GEDCOM Generation Service main loop...")

        # Start the timeout checker as a separate background task so it
        # never blocks the SQS poller.
        timeout_task = asyncio.create_task(
            self._timeout_checker_loop(),
            name="timeout-checker",
        )

        try:
            while self.running:
                try:
                    # Receive up to SQS_MAX_MESSAGES messages (long-poll).
                    messages = await self.sqs_consumer.receive_messages()

                    if messages:
                        # Route all messages from this batch concurrently.
                        # process_message() only enqueues work — it never
                        # awaits LLM calls — so this gather returns quickly.
                        await asyncio.gather(
                            *[self.process_message(m) for m in messages]
                        )
                    else:
                        # Brief sleep when the queue is empty.
                        await asyncio.sleep(1)

                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, shutting down...")
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    await asyncio.sleep(5)  # Back-off before retrying

        finally:
            # Cancel the timeout checker and wait for it to finish.
            timeout_task.cancel()
            try:
                await timeout_task
            except asyncio.CancelledError:
                pass

        logger.info("GEDCOM Generation Service stopped")

    # ------------------------------------------------------------------
    # SQS message routing (poller side — never awaits LLM calls)
    # ------------------------------------------------------------------

    async def process_message(self, message: dict) -> None:
        """
        Parse one SQS message and route it to the per-document pipeline.

        This method is intentionally lightweight: it parses the message,
        updates the DocumentGrouper, enqueues a work item on the per-document
        asyncio.Queue, and spawns a PageProcessorTask if one is not already
        running.  It does NOT await any LLM calls.

        Args:
            message: Raw SQS message dict from SQSConsumer.receive_messages()
        """
        parsed = self.sqs_consumer.parse_message(message)
        document_id = parsed["metadata"].get("document_id", "unknown")

        try:
            # Idempotency check — skip documents already fully processed.
            if await self.document_grouper.is_already_processed(document_id):
                logger.info(
                    f"Document {document_id} already processed. Skipping."
                )
                await self.sqs_consumer.delete_message(parsed["receipt_handle"])
                return

            # Register the page with the grouper (updates expected_pages,
            # metadata, last_updated timestamp, duplicate-page detection, …).
            await self.document_grouper.add_message(parsed)

            # Determine the 1-based page index for this arrival.
            async with self._state_lock:
                idx = self._page_indices.get(document_id, 0) + 1
                self._page_indices[document_id] = idx

            # Check whether the document is now complete.
            is_complete, completion_reason = await self.document_grouper.is_complete(
                document_id
            )

            # Retrieve the document-level metadata from the group (set by
            # the first message that arrived for this document).
            group = await self.document_grouper.get_group(document_id)
            document_metadata = group.metadata if group else parsed["metadata"]
            expected_pages = group.expected_pages if group else None

            # Log progress for incomplete documents.
            if not is_complete and group:
                page_numbers = sorted(
                    p
                    for p in group.get_page_numbers()
                    if p is not None
                )
                logger.info(
                    f"Document {document_id} is incomplete. "
                    f"Received: {len(group.messages)} message(s), "
                    f"Expected: {expected_pages or 'unknown'}, "
                    f"Pages: {page_numbers}, "
                    f"Waiting for more pages..."
                )

            # Get or create the per-document asyncio.Queue.
            queue = await self.document_grouper.get_or_create_queue(
                document_id,
                maxsize=Config.PAGE_QUEUE_MAX_SIZE,
            )

            # Build the work item for the PageProcessorTask.
            work_item = {
                "message": parsed,
                "page_index": idx,
                "document_metadata": document_metadata,
                "total_pages": expected_pages or idx,  # best-known value
                "is_last": is_complete,
                "completion_reason": completion_reason,
            }
            
            # Use non-blocking queue put to prevent SQS poller from blocking
            # when queue is full. Apply back-pressure by delaying message retry.
            try:
                queue.put_nowait(work_item)
            except asyncio.QueueFull:
                logger.warning(
                    f"Queue full for document {document_id} "
                    f"(size: {queue.qsize()}/{queue.maxsize}), "
                    f"applying back-pressure - message will retry in "
                    f"{Config.QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT}s"
                )
                # Change message visibility to delay retry
                await self.sqs_consumer.change_message_visibility(
                    receipt_handle=parsed["receipt_handle"],
                    visibility_timeout=Config.QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT
                )
                return  # Don't delete message, let SQS retry

            # Spawn a PageProcessorTask for this document if one is not
            # already running (or if the previous one has already finished).
            existing_task = self.document_grouper.processor_tasks.get(document_id)
            if existing_task is None or existing_task.done():
                task = asyncio.create_task(
                    self._page_processor_task(document_id, queue),
                    name=f"processor-{document_id}",
                )
                self.document_grouper.processor_tasks[document_id] = task
                logger.info(
                    f"Spawned PageProcessorTask for document {document_id}"
                )

            # Delete the SQS message immediately — the page is now safely
            # buffered in the in-memory queue.
            await self.sqs_consumer.delete_message(parsed["receipt_handle"])

        except Exception as e:
            logger.error(
                f"Error routing message for document {document_id}: {e}",
                exc_info=True,
            )
            # Do NOT delete the message — let it become visible again for retry.

    # ------------------------------------------------------------------
    # PageProcessorTask — one per active document
    # ------------------------------------------------------------------

    async def _page_processor_task(
        self,
        document_id: str,
        queue: asyncio.Queue,
    ) -> None:
        """
        Long-lived coroutine that drains the per-document page queue.

        Runs concurrently with the SQS poller.  Processes pages one at a
        time (preserving the sequential rolling-context chain) and performs
        all post-generation steps (validate, upload, publish) before moving
        to the next page.

        Terminates when:
        - A work item with ``is_last=True`` has been processed, OR
        - A sentinel (``None``) is received (timeout or shutdown signal).

        Args:
            document_id: Document identifier.
            queue: Per-document asyncio.Queue populated by process_message().
        """
        logger.info(f"PageProcessorTask started for document {document_id}")

        # Initialise rolling context for this document.
        async with self._state_lock:
            if document_id not in self._rolling_contexts:
                self._rolling_contexts[document_id] = (
                    self.context_extractor.initial_context()
                    if self.context_extractor is not None
                    else ""
                )

        generation_start = time.time()

        try:
            while True:
                # Block until the next work item (or sentinel) is available.
                work_item = await queue.get()

                try:
                    # Sentinel → document timed out or service is shutting down.
                    if work_item is _QUEUE_SENTINEL:
                        logger.info(
                            f"PageProcessorTask received sentinel for "
                            f"{document_id}, flushing and stopping."
                        )
                        break

                    message = work_item["message"]
                    page_index = work_item["page_index"]
                    page_number = message["metadata"].get("page_number")
                    document_metadata = work_item["document_metadata"]
                    total_pages = work_item["total_pages"]
                    is_last = work_item["is_last"]
                    completion_reason = work_item["completion_reason"]

                    page_label = (
                        page_number if page_number is not None else f"#{page_index}"
                    )

                    # Retrieve current rolling context.
                    async with self._state_lock:
                        rolling_context = self._rolling_contexts.get(
                            document_id, ""
                        )

                    # ---- GEDCOM generation (LLM call) ----
                    try:
                        gedcom_content, updated_context = (
                            await self.gedcom_generator.generate_single_page(
                                message=message,
                                document_metadata=document_metadata,
                                page_index=page_index,
                                total_pages=total_pages,
                                rolling_context=rolling_context,
                                document_id=document_id,
                            )
                        )
                    except Exception as gen_err:
                        logger.error(
                            f"GEDCOM generation failed for {document_id} "
                            f"page {page_label}: {gen_err}",
                            exc_info=True,
                        )
                        langfuse_tracer.log_error(
                            gen_err,
                            context={
                                "document_id": document_id,
                                "page_number": page_number,
                                "page_index": page_index,
                                "operation": "gedcom_generation",
                            },
                        )
                        # Apply per-page retry logic.
                        if page_number is not None:
                            group = await self.document_grouper.get_group(
                                document_id
                            )
                            if group:
                                retry_count = group.increment_page_retry(
                                    page_number
                                )
                                if not group.should_retry_page(
                                    page_number,
                                    max_retries=Config.MAX_PAGE_RETRIES,
                                ):
                                    logger.error(
                                        f"Page {page_label} of document "
                                        f"{document_id} exceeded max retries "
                                        f"({Config.MAX_PAGE_RETRIES}). "
                                        f"Marking as permanently failed."
                                    )
                                    langfuse_tracer.log_error(
                                        ValueError(
                                            f"Page {page_label} permanently "
                                            f"failed after {retry_count} retries"
                                        ),
                                        context={
                                            "document_id": document_id,
                                            "page_number": page_number,
                                            "retry_count": retry_count,
                                            "max_retries": Config.MAX_PAGE_RETRIES,
                                            "operation": "max_retries_exceeded",
                                        },
                                        level="ERROR",
                                    )
                                    group.mark_page_processed(page_number)
                                else:
                                    logger.warning(
                                        f"Page {page_label} of document "
                                        f"{document_id} will be retried "
                                        f"(attempt {retry_count}/"
                                        f"{Config.MAX_PAGE_RETRIES})"
                                    )
                                    await queue.put(work_item)
                                    continue
                        # Continue to next page — do not abort the whole document.
                        if is_last:
                            break
                        continue

                    # Update rolling context for the next page.
                    async with self._state_lock:
                        self._rolling_contexts[document_id] = updated_context

                    # ---- Post-processing: validate, upload, publish ----
                    generation_time = time.time() - generation_start
                    try:
                        await self._process_page_result(
                            document_id=document_id,
                            page_index=page_index,
                            page_number=page_number,
                            gedcom_content=gedcom_content,
                            message=message,
                            document_metadata=document_metadata,
                            completion_reason=completion_reason,
                            generation_time=generation_time,
                        )

                        # Mark page as successfully processed.
                        if page_number is not None:
                            group = await self.document_grouper.get_group(
                                document_id
                            )
                            if group:
                                group.mark_page_processed(page_number)

                    except Exception as post_err:
                        logger.error(
                            f"Post-processing failed for {document_id} "
                            f"page {page_label}: {post_err}",
                            exc_info=True,
                        )
                        langfuse_tracer.log_error(
                            post_err,
                            context={
                                "document_id": document_id,
                                "page_number": page_number,
                                "page_index": page_index,
                                "operation": "per_page_processing",
                            },
                        )
                        # Apply per-page retry logic.
                        if page_number is not None:
                            group = await self.document_grouper.get_group(
                                document_id
                            )
                            if group:
                                retry_count = group.increment_page_retry(
                                    page_number
                                )
                                if not group.should_retry_page(
                                    page_number,
                                    max_retries=Config.MAX_PAGE_RETRIES,
                                ):
                                    logger.error(
                                        f"Page {page_label} of document "
                                        f"{document_id} exceeded max retries "
                                        f"({Config.MAX_PAGE_RETRIES}). "
                                        f"Marking as permanently failed."
                                    )
                                    langfuse_tracer.log_error(
                                        ValueError(
                                            f"Page {page_label} permanently "
                                            f"failed after {retry_count} retries"
                                        ),
                                        context={
                                            "document_id": document_id,
                                            "page_number": page_number,
                                            "retry_count": retry_count,
                                            "max_retries": Config.MAX_PAGE_RETRIES,
                                            "operation": "max_retries_exceeded",
                                        },
                                        level="ERROR",
                                    )
                                    group.mark_page_processed(page_number)
                                else:
                                    logger.warning(
                                        f"Page {page_label} of document "
                                        f"{document_id} will be retried "
                                        f"(attempt {retry_count}/"
                                        f"{Config.MAX_PAGE_RETRIES})"
                                    )
                                    await queue.put(work_item)
                                    continue

                    if is_last:
                        logger.info(
                            f"PageProcessorTask: last page processed for "
                            f"document {document_id} "
                            f"(reason: {completion_reason})"
                        )
                        break

                finally:
                    queue.task_done()

        except Exception as e:
            logger.error(
                f"Unexpected error in PageProcessorTask for {document_id}: {e}",
                exc_info=True,
            )
            langfuse_tracer.log_error(
                e,
                context={
                    "document_id": document_id,
                    "operation": "page_processor_task",
                },
            )

        finally:
            # ---- Cleanup ----
            await self.document_grouper.mark_as_processed(document_id)
            await self.document_grouper.remove_group(document_id)
            await self.document_grouper.remove_queue(document_id)
            async with self._state_lock:
                self._rolling_contexts.pop(document_id, None)
                self._page_indices.pop(document_id, None)
            logger.info(
                f"PageProcessorTask finished and cleaned up for document "
                f"{document_id}"
            )

    # ------------------------------------------------------------------
    # Per-page post-processing (validate + upload + publish)
    # ------------------------------------------------------------------

    @langfuse_tracer.observe(name="process-page-result")
    async def _process_page_result(
        self,
        document_id: str,
        page_index: int,
        page_number: Optional[int],
        gedcom_content: str,
        message: dict,
        document_metadata: dict,
        completion_reason: str,
        generation_time: float,
    ) -> None:
        """
        Validate, upload, and publish the GEDCOM output for a single page.

        This is the extracted body of the former
        ``process_complete_document()`` per-page loop.  All Langfuse score
        logging, validation, S3 upload, and SQS publish logic is preserved
        verbatim.

        Args:
            document_id: Document identifier.
            page_index: 1-based index of this page within the document group.
            page_number: Original page number from metadata (may be None).
            gedcom_content: Raw GEDCOM string produced by the LLM.
            message: Original parsed SQS message for this page.
            document_metadata: Document-level metadata dict.
            completion_reason: "all_pages_received" | "timeout_reached" | …
            generation_time: Wall-clock seconds elapsed since generation started
                (used for processing_time_ms in the outbound SQS message).
        """
        page_suffix = (
            f"p{page_number}" if page_number is not None else f"p{page_index}"
        )
        page_label = page_number if page_number is not None else f"#{page_index}"

        # ---- Count records ----
        record_counts = self.gedcom_generator.count_gedcom_records(gedcom_content)

        # ---- Langfuse score metrics ----
        langfuse_tracer.add_score(
            name="total_persons",
            value=record_counts["total_persons"],
            comment=f"Total persons in document {document_id} page {page_label}",
        )
        langfuse_tracer.add_score(
            name="individuals_processed",
            value=record_counts["individuals"],
            comment=f"Individuals in document {document_id} page {page_label}",
        )
        langfuse_tracer.add_score(
            name="families_processed",
            value=record_counts["families"],
            comment=f"Families in document {document_id} page {page_label}",
        )
        langfuse_tracer.add_score(
            name="baptisms_processed",
            value=record_counts["baptisms"],
            comment=f"Baptisms in document {document_id} page {page_label}",
        )
        langfuse_tracer.add_score(
            name="deaths_processed",
            value=record_counts["deaths"],
            comment=f"Deaths in document {document_id} page {page_label}",
        )
        langfuse_tracer.add_score(
            name="marriages_processed",
            value=record_counts["marriages"],
            comment=f"Marriages in document {document_id} page {page_label}",
        )
        langfuse_tracer.add_score(
            name="total_events",
            value=record_counts["total_events"],
            comment=f"Total events in document {document_id} page {page_label}",
        )

        # ---- Validate GEDCOM ----
        validation_status = "valid"
        if Config.ENABLE_GEDCOM_VALIDATION:
            try:
                is_valid, errors = self.gedcom_validator.validate(gedcom_content)
                validation_status = "valid" if is_valid else "invalid"

                if not is_valid:
                    logger.warning(
                        f"GEDCOM validation failed for {document_id} "
                        f"page {page_label}: {len(errors)} error(s)"
                    )
                    for error in errors[:5]:
                        logger.warning(f"  - {error}")

                    langfuse_tracer.log_error(
                        ValueError(
                            f"GEDCOM validation failed: {len(errors)} errors"
                        ),
                        context={
                            "document_id": document_id,
                            "page_number": page_number,
                            "operation": "gedcom_validation",
                            "error_count": len(errors),
                            "sample_errors": errors[:5],
                        },
                        level="WARNING",
                    )
            except Exception as e:
                logger.error(
                    f"GEDCOM validation error for {document_id} "
                    f"page {page_label}: {e}"
                )
                langfuse_tracer.log_error(
                    e,
                    context={
                        "document_id": document_id,
                        "page_number": page_number,
                        "operation": "gedcom_validation",
                    },
                )
                # Continue processing even if validation itself errors.

        # ---- Upload to S3 ----
        page_filename = f"{document_id}_{page_suffix}.ged"
        source_image_uri = message.get("source_image", {}).get("s3_uri")

        s3_uri = await self._upload_to_s3(
            document_id=document_id,
            gedcom_content=gedcom_content,
            filename=page_filename,
            source_image_uri=source_image_uri,
        )

        # ---- Retrieve group for total-pages count ----
        group = await self.document_grouper.get_group(document_id)
        num_pages_total = (
            group.expected_pages or len(group.messages)
            if group
            else page_index
        )

        # ---- Build and publish GEDCOM-ready message ----
        gedcom_ready_message = {
            "document_metadata": {
                "document_id": document_id,
                "document_title": document_metadata.get("document_title", ""),
                "date_range": document_metadata.get("date_range", ""),
                "location": document_metadata.get("location", ""),
                "total_pages": num_pages_total,
                "page_number": page_number,
                "page_index": page_index,
                "completion_reason": completion_reason,
            },
            "gedcom_data": {
                "content": gedcom_content,
                "filename": page_filename,
                "s3_uri": s3_uri,
                "validation_status": validation_status,
                "individual_count": record_counts["individuals"],
                "family_count": record_counts["families"],
                "baptism_count": record_counts["baptisms"],
                "death_count": record_counts["deaths"],
                "marriage_count": record_counts["marriages"],
                "total_events": record_counts["total_events"],
            },
            "source_ocr_uris": [
                message.get("ocr_result", {}).get("s3_uri", "")
            ],
            "metadata": {
                "processing_time_ms": int(generation_time * 1000),
                "openrouter_model": Config.OPENROUTER_MODEL,
            },
        }

        await self._publish_to_sqs(gedcom_ready_message)

        logger.info(
            f"Successfully processed document {document_id} "
            f"page {page_label}: "
            f"{record_counts['individuals']} individuals, "
            f"{record_counts['families']} families, "
            f"{record_counts['baptisms']} baptisms, "
            f"{record_counts['deaths']} deaths, "
            f"{record_counts['marriages']} marriages, "
            f"validation: {validation_status}"
        )

    # ------------------------------------------------------------------
    # Timeout checker (background task)
    # ------------------------------------------------------------------

    async def _timeout_checker_loop(self) -> None:
        """
        Background task that periodically checks for timed-out documents.

        Runs every GROUPING_CHECK_INTERVAL seconds.  When a document has not
        received all its pages within GROUPING_TIMEOUT_SECONDS of the last
        message, a sentinel is placed on its queue so the PageProcessorTask
        flushes whatever pages it has and terminates.
        """
        logger.info("Timeout checker loop started")
        while self.running:
            try:
                await asyncio.sleep(Config.GROUPING_CHECK_INTERVAL)

                timed_out = await self.document_grouper.check_timeouts()

                for doc_id in timed_out:
                    logger.warning(
                        f"Document {doc_id} timed out after "
                        f"{Config.GROUPING_TIMEOUT_SECONDS}s — "
                        f"sending sentinel to processor task."
                    )
                    queue = await self.document_grouper.get_or_create_queue(
                        doc_id,
                        maxsize=Config.PAGE_QUEUE_MAX_SIZE,
                    )
                    await queue.put(_QUEUE_SENTINEL)

            except asyncio.CancelledError:
                logger.info("Timeout checker loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error in timeout checker loop: {e}", exc_info=True
                )

        logger.info("Timeout checker loop stopped")

    # ------------------------------------------------------------------
    # Private helpers (thin wrappers kept for clarity)
    # ------------------------------------------------------------------

    async def _upload_to_s3(
        self,
        document_id: str,
        gedcom_content: str,
        filename: Optional[str] = None,
        source_image_uri: Optional[str] = None,
    ) -> str:
        """Upload GEDCOM content to S3 and return the S3 URI."""
        if filename is None:
            filename = f"{document_id}.ged"
        return await self.s3_handler.upload_gedcom(
            content=gedcom_content,
            document_id=document_id,
            filename=filename,
            source_s3_uri=source_image_uri,
            preserve_structure=True,
        )

    async def _publish_to_sqs(self, gedcom_ready_message: dict) -> None:
        """Publish a GEDCOM-ready message to the output SQS queue."""
        await self.sqs_publisher.publish_gedcom_ready(
            document_metadata=gedcom_ready_message["document_metadata"],
            gedcom_data=gedcom_ready_message["gedcom_data"],
            source_ocr_uris=gedcom_ready_message["source_ocr_uris"],
            processing_metadata=gedcom_ready_message["metadata"],
        )

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """
        Graceful shutdown.

        1. Signals the main loop to stop.
        2. Sends a sentinel to every active per-document queue so their
           PageProcessorTasks can finish the page they are currently working
           on and then exit cleanly.
        3. Waits for all processor tasks to complete.
        4. Closes the OpenRouter client and flushes Langfuse traces.
        """
        logger.info("Shutting down GEDCOM Generation Service...")
        self.running = False

        # Signal all active processor tasks to stop after their current page.
        active_doc_ids = list(self.document_grouper.page_queues.keys())
        for doc_id in active_doc_ids:
            queue = self.document_grouper.page_queues.get(doc_id)
            if queue is not None:
                logger.info(
                    f"Sending shutdown sentinel to processor task for "
                    f"document {doc_id}"
                )
                await queue.put(_QUEUE_SENTINEL)

        # Wait for all processor tasks to finish.
        active_tasks = [
            t
            for t in self.document_grouper.processor_tasks.values()
            if t is not None and not t.done()
        ]
        if active_tasks:
            logger.info(
                f"Waiting for {len(active_tasks)} processor task(s) to finish..."
            )
            await asyncio.gather(*active_tasks, return_exceptions=True)

        # Close OpenRouter client.
        await self.openrouter_client.close()

        # Flush Langfuse traces.
        langfuse_tracer.flush()

        logger.info("Shutdown complete")


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

async def main():
    """Main entry point."""
    service = None

    try:
        service = GedcomGenerationService()

        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            if service:
                asyncio.create_task(service.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        await service.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if service:
            await service.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
