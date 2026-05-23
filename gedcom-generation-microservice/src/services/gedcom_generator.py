"""
GEDCOM generator service that uses OpenRouter LLM to generate GEDCOM directly.
"""

from typing import Optional
from .openrouter_client import OpenRouterClient
from .metadata_formatter import MetadataFormatter
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
        gedcom_version: str = "5.5.1"
    ):
        """
        Initialize GEDCOM generator.
        
        Args:
            openrouter_client: OpenRouter client for LLM calls
            gedcom_version: GEDCOM version to generate (default: 5.5.1)
        """
        self.openrouter_client = openrouter_client
        self.gedcom_version = gedcom_version
        self.metadata_formatter = MetadataFormatter()
        
        logger.info(f"Initialized GEDCOM generator (version {gedcom_version})")
    
    @langfuse_tracer.observe(name="gedcom-generation")
    async def generate_from_document_group(
        self,
        sorted_messages: list,
        document_metadata: dict
    ) -> str:
        """
        Generate GEDCOM from a complete document group.
        
        Args:
            sorted_messages: List of OCR messages sorted by page number
            document_metadata: Document-level metadata
        
        Returns:
            Generated GEDCOM content as string
        
        Raises:
            ValueError: If generation fails
        """
        document_id = document_metadata.get('document_id', 'unknown')
        logger.info(f"Generating GEDCOM for document: {document_id}")
        
        try:
            # Format document with metadata
            formatted_document = await self._format_document(sorted_messages, document_metadata)
            
            # Get system prompt
            system_prompt = get_gedcom_system_prompt(self.gedcom_version)
            
            # Generate GEDCOM via LLM (automatically traced by @observe decorator)
            gedcom_content = await self.openrouter_client.generate_gedcom(
                formatted_document,
                system_prompt
            )
            
            logger.info(
                f"Successfully generated GEDCOM: {len(gedcom_content)} bytes"
            )
            
            return gedcom_content
            
        except Exception as e:
            logger.error(f"Failed to generate GEDCOM: {e}")
            raise ValueError(f"GEDCOM generation failed: {e}")
    
    @langfuse_tracer.observe(name="format-document")
    async def _format_document(
        self,
        sorted_messages: list,
        document_metadata: dict
    ) -> str:
        """
        Format document with metadata.
        
        Args:
            sorted_messages: List of OCR messages sorted by page number
            document_metadata: Document-level metadata
            
        Returns:
            Formatted document string
        """
        formatted_document = self.metadata_formatter.format_document(
            sorted_messages,
            document_metadata
        )
        return formatted_document
    
    def count_gedcom_records(self, gedcom_content: str) -> dict:
        """
        Count individuals and families in GEDCOM content.
        
        Args:
            gedcom_content: GEDCOM file content
        
        Returns:
            Dictionary with counts: {individuals, families}
        """
        lines = gedcom_content.split('\n')
        
        individual_count = 0
        family_count = 0
        
        for line in lines:
            if line.startswith('0 @I') and '@ INDI' in line:
                individual_count += 1
            elif line.startswith('0 @F') and '@ FAM' in line:
                family_count += 1
        
        return {
            "individuals": individual_count,
            "families": family_count
        }
