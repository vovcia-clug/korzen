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
            try:
                formatted_document = await self._format_document(sorted_messages, document_metadata)
            except Exception as e:
                logger.error(f"Failed to format document {document_id}: {e}")
                langfuse_tracer.log_error(
                    e,
                    context={
                        "document_id": document_id,
                        "operation": "format_document",
                        "num_messages": len(sorted_messages)
                    }
                )
                raise ValueError(f"Document formatting failed: {e}")
            
            # Get system prompt
            system_prompt = get_gedcom_system_prompt(self.gedcom_version)
            
            # Generate GEDCOM via LLM (automatically traced by @observe decorator)
            try:
                gedcom_content = await self.openrouter_client.generate_gedcom(
                    formatted_document,
                    system_prompt
                )
            except Exception as e:
                logger.error(f"OpenRouter API call failed for {document_id}: {e}")
                langfuse_tracer.log_error(
                    e,
                    context={
                        "document_id": document_id,
                        "operation": "openrouter_api_call",
                        "formatted_document_length": len(formatted_document),
                        "model": self.openrouter_client.model
                    }
                )
                raise ValueError(f"LLM API call failed: {e}")
            
            logger.info(
                f"Successfully generated GEDCOM: {len(gedcom_content)} bytes"
            )
            
            return gedcom_content
            
        except ValueError:
            # Re-raise ValueError as-is (already logged)
            raise
        except Exception as e:
            logger.error(f"Failed to generate GEDCOM for {document_id}: {e}")
            langfuse_tracer.log_error(
                e,
                context={
                    "document_id": document_id,
                    "operation": "gedcom_generation"
                }
            )
            raise ValueError(f"GEDCOM generation failed: {e}")
    
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
