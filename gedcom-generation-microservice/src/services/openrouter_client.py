"""
OpenRouter API client for generating GEDCOM directly from formatted document text.

This service uses the OpenAI SDK to communicate with OpenRouter's API endpoint,
which is OpenAI-compatible. It handles retries, timeouts, and GEDCOM extraction.
"""

import asyncio
import json
import logging
import re
from typing import Optional
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

from ..utils.logger import get_logger
from ..config import Config
from ..utils import langfuse_tracer

logger = get_logger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API to generate GEDCOM files."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-flash-1.5",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: int = 300,
        max_retries: int = 3,
        retry_backoff_base: int = 2,
        retry_backoff_max: int = 60
    ):
        """
        Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key
            model: Model identifier to use
            base_url: OpenRouter API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_backoff_base: Base for exponential backoff
            retry_backoff_max: Maximum backoff time in seconds
        """
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
        
        # Log API key info for debugging (first 10 chars only)
        api_key_preview = api_key[:10] + "..." if len(api_key) > 10 else api_key
        logger.info(f"API key loaded: {api_key_preview} (length: {len(api_key)})")
        
        # Initialize OpenAI client pointing to OpenRouter
        logger.info("Initializing OpenRouter client")
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout
        )
        
        # SDK automatically adds Authorization header to all requests
        
        self.model = model
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.retry_backoff_max = retry_backoff_max
        
        logger.info(
            f"Initialized OpenRouter client with model: {model}, "
            f"base_url: {base_url}"
        )
    
    @langfuse_tracer.observe(name="openrouter-llm-call", as_type="generation")
    async def generate_gedcom(
        self,
        formatted_document: str,
        system_prompt: str
    ) -> str:
        """
        Generate GEDCOM content from formatted document text.
        
        Args:
            formatted_document: Formatted document with metadata and OCR text
            system_prompt: System prompt for GEDCOM generation
            
        Returns:
            Generated GEDCOM content as string
            
        Raises:
            APIError: If API call fails after retries
            ValueError: If response cannot be parsed
        """
        logger.info(
            f"Generating GEDCOM from {len(formatted_document)} characters of formatted text"
        )
        
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": formatted_document
            }
        ]
        
        # Retry loop for handling transient failures
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Attempt {attempt + 1}/{self.max_retries} to call OpenRouter API")
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.0,  # Deterministic output for data extraction
                    extra_headers={
                        # Authorization header is automatically added by OpenAI SDK
                        "HTTP-Referer": "https://github.com/korzen",
                        "X-Title": "GEDCOM Generation Service"
                    }
                )
                
                # Extract content from response
                content = response.choices[0].message.content
                
                if not content:
                    raise ValueError("Empty response from OpenRouter API")
                
                logger.debug(f"Received response: {len(content)} characters")
                
                # Extract GEDCOM from response (may be wrapped in markdown code blocks)
                gedcom_content = self._extract_gedcom(content)
                
                # Log success with token usage if available
                token_info = ""
                if response.usage:
                    token_info = f" (usage: {response.usage.total_tokens} tokens)"
                
                logger.info(
                    f"Successfully generated GEDCOM ({len(gedcom_content)} bytes){token_info}"
                )
                
                return gedcom_content
            
            except RateLimitError as e:
                last_error = e
                # Handle rate limiting with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = min(
                        self.retry_backoff_base ** attempt,
                        self.retry_backoff_max
                    )
                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time}s..."
                    )
                    # Log to Langfuse as warning (will retry)
                    langfuse_tracer.log_error(
                        e,
                        context={
                            "operation": "openrouter_api_call",
                            "error_type": "rate_limit",
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "retry_wait_seconds": wait_time,
                            "model": self.model
                        },
                        level="WARNING"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                    # Log final failure to Langfuse
                    langfuse_tracer.log_error(
                        e,
                        context={
                            "operation": "openrouter_api_call",
                            "error_type": "rate_limit_exceeded",
                            "attempts": self.max_retries,
                            "model": self.model
                        }
                    )
                    raise
                    
            except APITimeoutError as e:
                last_error = e
                # Handle timeouts with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = min(
                        self.retry_backoff_base ** attempt,
                        self.retry_backoff_max
                    )
                    logger.warning(
                        f"API timeout (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time}s..."
                    )
                    # Log to Langfuse as warning (will retry)
                    langfuse_tracer.log_error(
                        e,
                        context={
                            "operation": "openrouter_api_call",
                            "error_type": "timeout",
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "retry_wait_seconds": wait_time,
                            "model": self.model
                        },
                        level="WARNING"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"API timeout after {self.max_retries} attempts")
                    # Log final failure to Langfuse
                    langfuse_tracer.log_error(
                        e,
                        context={
                            "operation": "openrouter_api_call",
                            "error_type": "timeout_exceeded",
                            "attempts": self.max_retries,
                            "model": self.model
                        }
                    )
                    raise
                    
            except APIError as e:
                last_error = e
                # Handle other API errors
                logger.error(f"API error on attempt {attempt + 1}/{self.max_retries}: {str(e)}")
                
                # Log to Langfuse
                error_context = {
                    "operation": "openrouter_api_call",
                    "error_type": "api_error",
                    "attempt": attempt + 1,
                    "max_retries": self.max_retries,
                    "model": self.model,
                    "error_message": str(e)
                }
                
                if attempt < self.max_retries - 1:
                    wait_time = min(
                        self.retry_backoff_base ** attempt,
                        self.retry_backoff_max
                    )
                    logger.warning(f"Retrying in {wait_time}s...")
                    error_context["retry_wait_seconds"] = wait_time
                    langfuse_tracer.log_error(e, context=error_context, level="WARNING")
                    await asyncio.sleep(wait_time)
                else:
                    # Final failure
                    langfuse_tracer.log_error(e, context=error_context)
                    raise
                    
            except ValueError as e:
                # Parsing errors - no retry needed, this is a logic error
                logger.error(f"Failed to parse response: {str(e)}")
                langfuse_tracer.log_error(
                    e,
                    context={
                        "operation": "openrouter_response_parsing",
                        "error_type": "parsing_error",
                        "model": self.model
                    }
                )
                raise
        
        # Should not reach here due to raise in loop, but just in case
        if last_error:
            raise last_error
        raise ValueError("Failed to generate GEDCOM after all retries")
    
    def _extract_gedcom(self, content: str) -> str:
        """
        Extract GEDCOM content from API response.
        
        The LLM may wrap GEDCOM in markdown code blocks like:
        ```gedcom
        0 HEAD
        ...
        ```
        
        Or it may return plain GEDCOM directly.
        
        Args:
            content: Raw API response content
            
        Returns:
            Extracted GEDCOM content
            
        Raises:
            ValueError: If GEDCOM cannot be extracted
        """
        # Try to extract from markdown code block
        code_block_match = re.search(
            r'```(?:gedcom)?\s*\n(.*?)\n```',
            content,
            re.DOTALL | re.IGNORECASE
        )
        
        if code_block_match:
            gedcom_content = code_block_match.group(1).strip()
            logger.debug("Extracted GEDCOM from markdown code block")
            return gedcom_content
        
        # Check if content starts with GEDCOM header
        if content.strip().startswith("0 HEAD"):
            logger.debug("Content appears to be plain GEDCOM")
            return content.strip()
        
        # Try to find GEDCOM header anywhere in content
        gedcom_start = content.find("0 HEAD")
        if gedcom_start != -1:
            gedcom_content = content[gedcom_start:].strip()
            logger.debug("Found GEDCOM header in content")
            return gedcom_content
        
        # If we get here, we couldn't find valid GEDCOM
        logger.error("Could not extract GEDCOM from response")
        logger.debug(f"Response content (first 500 chars): {content[:500]}")
        raise ValueError("Response does not contain valid GEDCOM format")
    
    async def close(self):
        """Close the OpenAI client connection."""
        await self.client.close()
        logger.debug("OpenRouter client closed")
