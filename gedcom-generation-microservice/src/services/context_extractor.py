"""
Context extractor service that maintains a small rolling document-level context
carried forward between pages of a document, using the OpenRouter LLM.
"""

from typing import Optional
from .openrouter_client import OpenRouterClient
from ..prompts.context_extraction import (
    get_context_extraction_system_prompt,
    get_context_extraction_user_prompt,
)
from ..utils.logger import get_logger
from ..config import Config
from ..utils import langfuse_tracer

logger = get_logger(__name__)


class ContextExtractor:
    """Maintains a small, carried-forward document-level context across pages."""

    def __init__(
        self,
        openrouter_client: OpenRouterClient,
        enabled: bool = True,
        max_context_chars: int = 4000,
    ):
        """
        Args:
            openrouter_client: OpenRouter client for LLM calls (shared instance).
            enabled: Master on/off switch (Config.ENABLE_CONTEXT_EXTRACTION).
            max_context_chars: Hard cap on the carried-forward context length;
                the returned context is truncated if it exceeds this. Kept small
                because the context is document-level only (no per-person data).
        """
        self.openrouter_client = openrouter_client
        self.enabled = enabled
        self.max_context_chars = max_context_chars
        logger.info(
            f"Initialized ContextExtractor "
            f"(enabled={enabled}, max_context_chars={max_context_chars})"
        )

    @staticmethod
    def initial_context() -> str:
        """Return the empty starting context used before the first page."""
        return ""

    @langfuse_tracer.observe(name="context-extraction")
    async def update_context(
        self,
        current_context: str,
        page_content: str,
        page_index: int,
        total_pages: int,
        document_id: str = "unknown",
    ) -> str:
        """
        Produce the updated rolling context given the prior context and the
        current page.

        Args:
            current_context: Accumulated context so far ("" for the first page).
            page_content: Formatted current-page text
                (MetadataFormatter.format_single_page output).
            page_index: 1-based page index within the document group.
            total_pages: Total pages in the document group.
            document_id: Document identifier (for logging/tracing context).

        Returns:
            The updated context string. On any failure, returns current_context
            unchanged (fail-soft) so page GEDCOM generation is never blocked.
        """
        # Master switch: skip the LLM call entirely if disabled.
        if not self.enabled:
            return current_context

        # First-page short-circuit is NOT required: the prompt builder handles
        # empty context. We still log it for observability.
        is_first_page = not (current_context and current_context.strip())
        if is_first_page:
            logger.info(
                f"Context extraction for document {document_id}: first page "
                f"({page_index}/{total_pages}), starting from empty context"
            )

        system_prompt = get_context_extraction_system_prompt()
        user_prompt = get_context_extraction_user_prompt(
            current_context=current_context,
            page_content=page_content,
            page_index=page_index,
            total_pages=total_pages,
        )

        try:
            logger.info(
                f"Updating rolling context for document {document_id} "
                f"after page {page_index}/{total_pages}"
            )
            updated = await self.openrouter_client.generate_text(
                user_content=user_prompt,
                system_prompt=system_prompt,
            )
        except Exception as e:
            # Fail-soft: never block GEDCOM generation because context failed.
            logger.warning(
                f"Context extraction failed for document {document_id} "
                f"page {page_index}/{total_pages}; carrying forward prior "
                f"context unchanged: {e}"
            )
            langfuse_tracer.log_error(
                e,
                context={
                    "document_id": document_id,
                    "operation": "context_extraction",
                    "page_index": page_index,
                    "total_pages": total_pages,
                    "model": self.openrouter_client.model,
                },
                level="WARNING",
            )
            return current_context

        updated = (updated or "").strip()
        if not updated:
            logger.warning(
                f"Context extraction returned empty for document {document_id} "
                f"page {page_index}; keeping prior context"
            )
            return current_context

        # Enforce the max-length cap (keep the tail, which is most recent).
        if len(updated) > self.max_context_chars:
            logger.info(
                f"Truncating context for document {document_id} from "
                f"{len(updated)} to {self.max_context_chars} chars"
            )
            updated = updated[-self.max_context_chars:]

        logger.debug(
            f"Updated context for document {document_id} "
            f"({len(updated)} chars) after page {page_index}/{total_pages}"
        )
        return updated
