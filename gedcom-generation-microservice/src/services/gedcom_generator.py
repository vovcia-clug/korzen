"""
GEDCOM generator service that uses OpenRouter LLM to generate GEDCOM directly.
"""

from typing import Optional, List, Dict, Any, Tuple
from .openrouter_client import OpenRouterClient
from .metadata_formatter import MetadataFormatter
from .context_extractor import ContextExtractor
from ..prompts.gedcom_generation import get_gedcom_system_prompt
from ..utils.logger import get_logger
from ..config import Config
from ..utils import langfuse_tracer

logger = get_logger(__name__)


class GedcomGenerator:
    """Generates GEDCOM files from formatted document text using LLM."""
    
    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        gedcom_version: str = "5.5.1",
        context_extractor: Optional["ContextExtractor"] = None
    ):
        """
        Initialize GEDCOM generator.
        
        Args:
            openrouter_client: OpenRouter client for LLM calls
            gedcom_version: GEDCOM version to generate (default: 5.5.1)
            context_extractor: Optional context extractor that maintains a
                rolling document-level context carried forward between pages.
                When None, existing single-page behavior is unchanged.
        """
        self.openrouter_client = openrouter_client
        self.gedcom_version = gedcom_version
        self.metadata_formatter = MetadataFormatter()
        self.context_extractor = context_extractor
        
        logger.info(f"Initialized GEDCOM generator (version {gedcom_version})")

    @langfuse_tracer.observe(name="gedcom-generation-page")
    async def generate_single_page(
        self,
        message: Dict[str, Any],
        document_metadata: Dict[str, Any],
        page_index: int,
        total_pages: int,
        rolling_context: str,
        document_id: str,
    ) -> Tuple[str, str]:
        """
        Generate GEDCOM for a single page and return the updated rolling context.

        This is the extracted inner-loop body of
        ``generate_pages_from_document_group()``, made callable independently
        so that the pipeline-parallelism layer in ``main.py`` can invoke it
        one page at a time without waiting for the full document to arrive.

        Args:
            message: Parsed SQS message for this page (contains metadata +
                ocr_result).
            document_metadata: Document-level metadata (title, location, …).
            page_index: 1-based index of this page within the document group.
            total_pages: Total number of pages expected in the document group.
                Pass the current best-known value; it may be updated as more
                pages arrive.
            rolling_context: Accumulated context string from all previous pages
                (empty string for the very first page).
            document_id: Document identifier used for logging and tracing.

        Returns:
            A 2-tuple ``(gedcom_content, updated_rolling_context)`` where
            *gedcom_content* is the raw GEDCOM string produced by the LLM and
            *updated_rolling_context* is the new context to carry forward to
            the next page (unchanged on context-extraction failure).

        Raises:
            ValueError: If page formatting or the LLM API call fails.
        """
        page_number = message.get("metadata", {}).get("page_number")
        page_label = page_number if page_number is not None else f"#{page_index}"

        system_prompt = get_gedcom_system_prompt(self.gedcom_version)

        # --- Format this single page (document metadata header + OCR text) ---
        try:
            formatted_page = self.metadata_formatter.format_single_page(
                message,
                document_metadata,
                page_index=page_index,
                total_pages=total_pages,
            )
        except Exception as e:
            logger.error(
                f"Failed to format page {page_label} of document {document_id}: {e}"
            )
            langfuse_tracer.log_error(
                e,
                context={
                    "document_id": document_id,
                    "operation": "format_single_page",
                    "page_index": page_index,
                    "page_number": page_number,
                },
            )
            raise ValueError(f"Page formatting failed: {e}")

        # --- Prepend carried-forward context (if any) ---
        if rolling_context:
            page_input = (
                "CONTEXT FROM PREVIOUS PAGES:\n"
                f"{rolling_context}\n\n"
                "---\n\n"
                f"{formatted_page}"
            )
        else:
            page_input = formatted_page

        # --- LLM call ---
        try:
            logger.info(
                f"Sending page {page_index}/{total_pages} "
                f"(page {page_label}) of document {document_id} to LLM"
            )
            page_gedcom = await self.openrouter_client.generate_gedcom(
                page_input,
                system_prompt,
            )
        except Exception as e:
            logger.error(
                f"OpenRouter API call failed for page {page_label} "
                f"of document {document_id}: {e}"
            )
            langfuse_tracer.log_error(
                e,
                context={
                    "document_id": document_id,
                    "operation": "openrouter_api_call",
                    "page_index": page_index,
                    "page_number": page_number,
                    "formatted_page_length": len(formatted_page),
                    "model": self.openrouter_client.model,
                },
            )
            raise ValueError(f"LLM API call failed for page {page_label}: {e}")

        # --- Update rolling context for the next page (fail-soft) ---
        updated_context = rolling_context
        if self.context_extractor is not None:
            updated_context = await self.context_extractor.update_context(
                current_context=rolling_context,
                page_content=formatted_page,
                page_index=page_index,
                total_pages=total_pages,
                document_id=document_id,
            )

        return page_gedcom, updated_context

    @langfuse_tracer.observe(name="gedcom-generation")
    async def generate_pages_from_document_group(
        self,
        sorted_messages: list,
        document_metadata: dict
    ) -> List[Dict[str, Any]]:
        """
        Generate one GEDCOM per page from a complete document group.
        
        Pages are processed SEQUENTIALLY by delegating to
        ``generate_single_page()`` for each page.  Kept for backward
        compatibility; the pipeline-parallelism path in ``main.py`` calls
        ``generate_single_page()`` directly.
        
        Args:
            sorted_messages: List of OCR messages sorted by page number
            document_metadata: Document-level metadata
        
        Returns:
            List of per-page result dicts, one per page, in page order. Each dict
            contains:
                - "page_index": 1-based index within the document group
                - "page_number": original page number (or None)
                - "gedcom_content": generated GEDCOM string for the page
                - "message": the original OCR message for the page
        
        Raises:
            ValueError: If generation fails for any page
        """
        document_id = document_metadata.get('document_id', 'unknown')
        total_pages = len(sorted_messages)
        logger.info(
            f"Generating GEDCOM for document: {document_id} "
            f"({total_pages} page(s), one GEDCOM per page, processed sequentially)"
        )
        
        if not sorted_messages:
            raise ValueError("No messages to generate GEDCOM from")
        
        # Initialize rolling, carried-forward context for the first page.
        rolling_context = (
            self.context_extractor.initial_context()
            if self.context_extractor is not None
            else ""
        )
        
        page_results: List[Dict[str, Any]] = []
        
        # Process each grouped page one by one (sequentially)
        for idx, message in enumerate(sorted_messages, start=1):
            page_number = message.get("metadata", {}).get("page_number")

            page_gedcom, rolling_context = await self.generate_single_page(
                message=message,
                document_metadata=document_metadata,
                page_index=idx,
                total_pages=total_pages,
                rolling_context=rolling_context,
                document_id=document_id,
            )

            page_results.append({
                "page_index": idx,
                "page_number": page_number,
                "gedcom_content": page_gedcom,
                "message": message
            })
        
        logger.info(
            f"Successfully generated {len(page_results)} per-page GEDCOM output(s) "
            f"for document {document_id}"
        )
        
        return page_results
    
    def count_gedcom_records(self, gedcom_content: str) -> dict:
        """
        Count individuals, families, and events in GEDCOM content.
        
        Args:
            gedcom_content: GEDCOM file content
        
        Returns:
            Dictionary with counts: {
                individuals, families, baptisms, deaths, marriages,
                total_persons, total_events
            }
        """
        lines = gedcom_content.split('\n')
        
        individual_count = 0
        family_count = 0
        baptism_count = 0
        death_count = 0
        marriage_count = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Count individuals (persons)
            if line.startswith('0 @I') and '@ INDI' in line:
                individual_count += 1
            # Count families
            elif line.startswith('0 @F') and '@ FAM' in line:
                family_count += 1
            # Count baptisms (BAPM or CHR tags)
            elif stripped.startswith('1 BAPM') or stripped.startswith('1 CHR'):
                baptism_count += 1
            # Count deaths
            elif stripped.startswith('1 DEAT'):
                death_count += 1
            # Count marriages
            elif stripped.startswith('1 MARR'):
                marriage_count += 1
        
        total_events = baptism_count + death_count + marriage_count
        
        return {
            "individuals": individual_count,
            "families": family_count,
            "baptisms": baptism_count,
            "deaths": death_count,
            "marriages": marriage_count,
            "total_persons": individual_count,
            "total_events": total_events
        }
