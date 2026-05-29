"""LLM prompts for GEDCOM generation."""

from .gedcom_generation import (
    get_gedcom_system_prompt,
    get_gedcom_user_prompt_template,
)
from .context_extraction import (
    get_context_extraction_system_prompt,
    get_context_extraction_user_prompt,
)

__all__ = [
    "get_gedcom_system_prompt",
    "get_gedcom_user_prompt_template",
    "get_context_extraction_system_prompt",
    "get_context_extraction_user_prompt",
]
