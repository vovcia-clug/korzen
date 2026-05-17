"""
OpenRouter API client for extracting structured genealogical data from OCR text.

This service uses the OpenAI SDK to communicate with OpenRouter's API endpoint,
which is OpenAI-compatible. It handles retries, timeouts, and JSON parsing/validation.
"""

import asyncio
import json
import logging
from typing import Optional
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

from ..config import Config
from ..models import ChurchRecordsDocument
from ..prompts.church_records_extraction import get_extraction_prompt


class OpenRouterClient:
    """Client for OpenRouter API to extract structured genealogical data."""
    
    def __init__(self, config: Config, logger: Optional[logging.Logger] = None):
        """
        Initialize OpenRouter client.
        
        Args:
            config: Configuration object containing API settings
            logger: Logger instance for logging operations
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        
        if not config.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required in configuration")
        
        # Initialize OpenAI client pointing to OpenRouter
        self.client = AsyncOpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            timeout=config.OPENROUTER_TIMEOUT,
        )
        
        self.model = config.OPENROUTER_MODEL
        self.max_retries = config.MAX_RETRIES
        self.retry_backoff_base = config.RETRY_BACKOFF_BASE
        self.retry_backoff_max = config.RETRY_BACKOFF_MAX
        
        self.logger.info(
            f"Initialized OpenRouter client with model: {self.model}, "
            f"base_url: {config.OPENROUTER_BASE_URL}"
        )
    
    async def extract_structured_data(self, markdown_text: str) -> ChurchRecordsDocument:
        """
        Extract structured genealogical data from OCR markdown text.
        
        Args:
            markdown_text: OCR output in markdown format
            
        Returns:
            ChurchRecordsDocument containing extracted records
            
        Raises:
            APIError: If API call fails after retries
            ValueError: If response cannot be parsed
        """
        self.logger.info(f"Extracting structured data from {len(markdown_text)} characters of OCR text")
        
        messages = get_extraction_prompt(markdown_text)
        
        # Retry loop for handling transient failures
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Attempt {attempt + 1}/{self.max_retries} to call OpenRouter API")
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.0,  # Deterministic output for data extraction
                    response_format={"type": "json_object"},  # Request JSON response
                )
                
                # Extract content from response
                content = response.choices[0].message.content
                
                if not content:
                    raise ValueError("Empty response from OpenRouter API")
                
                self.logger.debug(f"Received response: {len(content)} characters")
                
                # Parse and validate JSON response
                parsed_data = self._parse_and_validate(content)
                
                # Log success with token usage if available
                token_info = ""
                if response.usage:
                    token_info = f" (usage: {response.usage.total_tokens} tokens)"
                self.logger.info(
                    f"Successfully extracted {len(parsed_data.records)} records{token_info}"
                )
                
                return parsed_data
                
            except RateLimitError as e:
                # Handle rate limiting with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = min(
                        self.retry_backoff_base ** attempt,
                        self.retry_backoff_max
                    )
                    self.logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"Rate limit exceeded after {self.max_retries} attempts")
                    raise
                    
            except APITimeoutError as e:
                # Handle timeouts with exponential backoff
                if attempt < self.max_retries - 1:
                    wait_time = min(
                        self.retry_backoff_base ** attempt,
                        self.retry_backoff_max
                    )
                    self.logger.warning(
                        f"API timeout (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.error(f"API timeout after {self.max_retries} attempts")
                    raise
                    
            except APIError as e:
                # Handle other API errors
                self.logger.error(f"API error on attempt {attempt + 1}/{self.max_retries}: {str(e)}")
                if attempt < self.max_retries - 1:
                    wait_time = min(
                        self.retry_backoff_base ** attempt,
                        self.retry_backoff_max
                    )
                    self.logger.warning(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
                    
            except (json.JSONDecodeError, ValueError) as e:
                # JSON parsing errors - no retry needed, this is a logic error
                self.logger.error(f"Failed to parse response: {str(e)}")
                raise ValueError(f"Invalid JSON response from API: {str(e)}")
        
        # Should not reach here due to raise in loop
        raise ValueError("Failed to extract structured data after all retries")
    
    def _parse_and_validate(self, json_content: str) -> ChurchRecordsDocument:
        """
        Parse JSON response and validate with Pydantic models.
        
        Args:
            json_content: JSON string from API response
            
        Returns:
            Validated ChurchRecordsDocument
            
        Raises:
            ValueError: If JSON is invalid or doesn't match schema
        """
        try:
            # Parse JSON
            data = json.loads(json_content)
            
            # Handle case where model might wrap response in extra keys
            if "records" not in data and len(data) == 1:
                # Try to extract if wrapped in a single key
                key = list(data.keys())[0]
                if isinstance(data[key], dict) and "records" in data[key]:
                    data = data[key]
            
            # Validate with Pydantic
            church_records = ChurchRecordsDocument(**data)
            
            self.logger.debug(
                f"Validated {len(church_records.records)} records from API response"
            )
            
            return church_records
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error: {str(e)}")
            self.logger.debug(f"Raw content: {json_content[:500]}...")
            raise ValueError(f"Invalid JSON in API response: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Validation error: {str(e)}")
            self.logger.debug(f"Data structure: {json.dumps(data, indent=2)[:500]}...")
            
            # DIAGNOSTIC: Log first record structure to identify schema mismatch
            if isinstance(data, dict) and "records" in data and len(data["records"]) > 0:
                first_record = data["records"][0]
                self.logger.error("DIAGNOSTIC - First record structure:")
                self.logger.error(f"  - record_type: {first_record.get('record_type', 'MISSING')}")
                self.logger.error(f"  - person keys: {list(first_record.get('person', {}).keys())}")
                if "parents" in first_record and len(first_record["parents"]) > 0:
                    self.logger.error(f"  - first parent keys: {list(first_record['parents'][0].keys())}")
                if "witnesses" in first_record and len(first_record["witnesses"]) > 0:
                    self.logger.error(f"  - first witness keys: {list(first_record['witnesses'][0].keys())}")
                self.logger.error(f"  - Full first record: {json.dumps(first_record, indent=2)}")
            
            raise ValueError(f"Response doesn't match expected schema: {str(e)}")
    
    async def close(self):
        """Close the OpenAI client connection."""
        await self.client.close()
        self.logger.debug("OpenRouter client closed")
