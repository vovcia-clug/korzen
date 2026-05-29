"""
GEDCOM generator service that uses OpenRouter LLM to generate GEDCOM directly.
"""

from typing import Optional, List, Dict, Any
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
    
    @langfuse_tracer.observe(name="gedcom-generation")
    async def generate_pages_from_document_group(
        self,
        sorted_messages: list,
        document_metadata: dict
    ) -> List[Dict[str, Any]]:
        """
        Generate one GEDCOM per page from a complete document group.
        
        Pages are processed SEQUENTIALLY: each page (already grouped by the
        document grouper) is formatted and sent to the LLM one at a time. Each
        page produces its own independent GEDCOM output. The grouping logic
        itself is unchanged - this method still receives a fully grouped,
        page-sorted document and simply emits a separate result per page.
        
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
        
        # Get system prompt once (shared across all page calls)
        system_prompt = get_gedcom_system_prompt(self.gedcom_version)
        
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
            page_label = page_number if page_number is not None else f"#{idx}"
            
            # Format this single page (reuses document metadata header)
            try:
                formatted_page = self.metadata_formatter.format_single_page(
                    message,
                    document_metadata,
                    page_index=idx,
                    total_pages=total_pages
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
                        "page_index": idx,
                        "page_number": page_number
                    }
                )
                raise ValueError(f"Page formatting failed: {e}")
            
            # Generate GEDCOM for this page via LLM (sequential call)
            try:
                logger.info(
                    f"Sending page {idx}/{total_pages} "
                    f"(page {page_label}) of document {document_id} to LLM"
                )
                # Prepend carried-forward context (if any) to the page content.
                if rolling_context:
                    page_input = (
                        "CONTEXT FROM PREVIOUS PAGES:\n"
                        f"{rolling_context}\n\n"
                        "---\n\n"
                        f"{formatted_page}"
                    )
                else:
                    page_input = formatted_page
                
                page_gedcom = await self.openrouter_client.generate_gedcom(
                    page_input,
                    system_prompt
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
                        "page_index": idx,
                        "page_number": page_number,
                        "formatted_page_length": len(formatted_page),
                        "model": self.openrouter_client.model
                    }
                )
                raise ValueError(f"LLM API call failed for page {page_label}: {e}")
            
            # Carry context forward for the next page (fail-soft inside).
            if self.context_extractor is not None:
                rolling_context = await self.context_extractor.update_context(
                    current_context=rolling_context,
                    page_content=formatted_page,
                    page_index=idx,
                    total_pages=total_pages,
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
