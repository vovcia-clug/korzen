"""
Metadata formatter for creating structured LLM prompts from document groups.

Formats document metadata and OCR text into a structured format for GEDCOM generation.
"""

from typing import Dict, List, Any
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MetadataFormatter:
    """Formats document metadata and OCR text for LLM processing."""
    
    def format_document(
        self,
        sorted_messages: List[Dict[str, Any]],
        document_metadata: Dict[str, Any]
    ) -> str:
        """
        Format document with metadata header and sorted pages.
        
        Args:
            sorted_messages: List of messages sorted by page number
            document_metadata: Document-level metadata
        
        Returns:
            Formatted document string ready for LLM
        """
        if not sorted_messages:
            raise ValueError("No messages to format")
        
        logger.info(
            f"Formatting document with {len(sorted_messages)} pages: "
            f"{document_metadata.get('document_id')}"
        )
        
        # Build metadata header
        header = self._build_metadata_header(document_metadata, len(sorted_messages))
        
        # Build pages section
        pages = self._build_pages_section(sorted_messages)
        
        # Combine
        formatted = f"{header}\n\n{pages}"
        
        logger.debug(f"Formatted document: {len(formatted)} characters")
        
        return formatted
    
    def _build_metadata_header(
        self,
        metadata: Dict[str, Any],
        total_pages: int
    ) -> str:
        """
        Build metadata header section.
        
        Args:
            metadata: Document metadata
            total_pages: Number of pages in document
        
        Returns:
            Formatted metadata header
        """
        lines = ["DOCUMENT METADATA:"]
        
        # Add available metadata fields
        if metadata.get("document_title"):
            lines.append(f"Title: {metadata['document_title']}")
        
        if metadata.get("location"):
            lines.append(f"Location: {metadata['location']}")
        
        if metadata.get("date_range"):
            lines.append(f"Date Range: {metadata['date_range']}")
        
        if metadata.get("record_type"):
            record_type = metadata['record_type'].replace('_', ' ').title()
            lines.append(f"Record Type: {record_type} Records")
        
        if metadata.get("language"):
            language = metadata['language'].title()
            lines.append(f"Language: {language}")
        
        lines.append(f"Total Pages: {total_pages}")
        
        if metadata.get("source"):
            source = metadata['source'].replace('_', ' ').title()
            lines.append(f"Source: {source}")
        
        return "\n".join(lines)
    
    def _build_pages_section(
        self,
        sorted_messages: List[Dict[str, Any]]
    ) -> str:
        """
        Build pages section with OCR text.
        
        Args:
            sorted_messages: List of messages sorted by page number
        
        Returns:
            Formatted pages section
        """
        pages = []
        
        for idx, message in enumerate(sorted_messages, start=1):
            page_number = message.get("metadata", {}).get("page_number")
            
            # Use actual page number if available, otherwise use sequential index
            if page_number is not None:
                page_label = str(page_number)
            else:
                page_label = f"{idx} (page number unknown)"
            
            ocr_result = message.get("ocr_result", {})
            markdown_text = ocr_result.get("markdown_text", "")
            
            # Format page
            page_section = f"---\nPAGE {page_label}:\n\n{markdown_text}\n"
            pages.append(page_section)
        
        return "\n".join(pages)
    
    def get_document_summary(
        self,
        document_metadata: Dict[str, Any],
        page_count: int
    ) -> str:
        """
        Get a brief summary of the document for logging.
        
        Args:
            document_metadata: Document metadata
            page_count: Number of pages
        
        Returns:
            Summary string
        """
        parts = []
        
        if document_metadata.get("document_title"):
            parts.append(document_metadata["document_title"])
        
        if document_metadata.get("date_range"):
            parts.append(f"({document_metadata['date_range']})")
        
        parts.append(f"{page_count} pages")
        
        return " ".join(parts)
