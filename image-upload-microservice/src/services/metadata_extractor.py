"""Metadata extraction service for Skanoteka URLs.

This module extracts metadata from Skanoteka genealogy archive URLs,
including place, unit, years, and page information.
"""

import re
from typing import Dict, Optional
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MetadataExtractor:
    """Extracts metadata from Skanoteka URLs."""

    def __init__(self, timeout: int = 30):
        """Initialize the metadata extractor.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        logger.info("metadata_extractor_initialized", timeout=timeout)

    def is_skanoteka_url(self, url: str) -> bool:
        """Check if a URL is from Skanoteka.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is from Skanoteka, False otherwise
        """
        if not url:
            return False
        return "skanoteka.genealodzy.pl" in url.lower()

    def extract_metadata_from_url(self, url: str) -> Dict[str, Optional[str]]:
        """Extract metadata from a Skanoteka page URL.
        
        Args:
            url: The Skanoteka page URL to extract metadata from
            
        Returns:
            Dictionary with keys: place, unit, years, page, source_url
            Returns error key if extraction fails
            
        Example:
            >>> extractor = MetadataExtractor()
            >>> metadata = extractor.extract_metadata_from_url(
            ...     "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg"
            ... )
            >>> print(metadata)
            {
                'place': 'Bolechów',
                'unit': '4500 M-1874-1937-Bolechów',
                'years': '1874-1937',
                'page': '301.jpg (301 z 303)',
                'source_url': 'https://skanoteka.genealodzy.pl/...'
            }
        """
        logger.info("extracting_metadata_from_url", url=url)
        
        if not self.is_skanoteka_url(url):
            logger.warning("not_skanoteka_url", url=url)
            return {
                "place": None,
                "unit": None,
                "years": None,
                "page": None,
                "source_url": url,
                "error": "Not a Skanoteka URL"
            }
        
        try:
            headers = {"User-Agent": self.user_agent}
            
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Find the sidebar div containing metadata
            sidebar = soup.find("div", class_="sidebar")
            
            if not sidebar:
                logger.warning("sidebar_not_found", url=url)
                return {
                    "place": None,
                    "unit": None,
                    "years": None,
                    "page": None,
                    "source_url": url,
                    "error": "Sidebar not found"
                }
            
            # Extract text content from sidebar
            sidebar_text = sidebar.get_text()
            
            # Extract metadata using regex patterns
            metadata = {
                "source_url": url
            }
            
            # Extract Miejscowość (place)
            place_match = re.search(r"Miejscowość:\s*\n\s*([^\n]+)", sidebar_text)
            metadata["place"] = place_match.group(1).strip() if place_match else None
            
            # Extract Jednostka (unit)
            unit_match = re.search(r"Jednostka:\s*\n\s*([^\n]+)", sidebar_text)
            metadata["unit"] = unit_match.group(1).strip() if unit_match else None
            
            # Extract Lata (years)
            years_match = re.search(r"Lata:\s*\n\s*([^\n]+)", sidebar_text)
            metadata["years"] = years_match.group(1).strip() if years_match else None
            
            # Extract Plik (page/file)
            file_match = re.search(r"Plik:\s*\n\s*([^\n]+)", sidebar_text)
            metadata["page"] = file_match.group(1).strip() if file_match else None
            
            logger.info(
                "metadata_extracted_successfully",
                url=url,
                place=metadata["place"],
                unit=metadata["unit"],
                years=metadata["years"],
                page=metadata["page"],
            )
            
            return metadata
            
        except requests.RequestException as e:
            logger.error(
                "metadata_extraction_request_failed",
                url=url,
                error=str(e),
                exc_info=True,
            )
            return {
                "place": None,
                "unit": None,
                "years": None,
                "page": None,
                "source_url": url,
                "error": f"Request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(
                "metadata_extraction_failed",
                url=url,
                error=str(e),
                exc_info=True,
            )
            return {
                "place": None,
                "unit": None,
                "years": None,
                "page": None,
                "source_url": url,
                "error": f"Extraction failed: {str(e)}"
            }

    def extract_metadata_from_filename(self, file_path: Path) -> Optional[Dict[str, Optional[str]]]:
        """Attempt to extract Skanoteka URL from filename or associated metadata file.
        
        This method looks for a companion .txt or .url file with the same name
        that might contain the source URL.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Metadata dictionary if URL found and extracted, None otherwise
        """
        # Check for companion .txt file
        txt_file = file_path.with_suffix(".txt")
        if txt_file.exists():
            try:
                content = txt_file.read_text(encoding="utf-8").strip()
                if self.is_skanoteka_url(content):
                    logger.info(
                        "found_url_in_companion_file",
                        file=str(file_path),
                        txt_file=str(txt_file),
                    )
                    return self.extract_metadata_from_url(content)
            except Exception as e:
                logger.warning(
                    "failed_to_read_companion_file",
                    file=str(file_path),
                    txt_file=str(txt_file),
                    error=str(e),
                )
        
        # Check for .url file (Windows URL shortcut format)
        url_file = file_path.with_suffix(".url")
        if url_file.exists():
            try:
                content = url_file.read_text(encoding="utf-8")
                # Parse .url file format
                url_match = re.search(r"URL=(.+)", content)
                if url_match:
                    url = url_match.group(1).strip()
                    if self.is_skanoteka_url(url):
                        logger.info(
                            "found_url_in_url_file",
                            file=str(file_path),
                            url_file=str(url_file),
                        )
                        return self.extract_metadata_from_url(url)
            except Exception as e:
                logger.warning(
                    "failed_to_read_url_file",
                    file=str(file_path),
                    url_file=str(url_file),
                    error=str(e),
                )
        
        logger.debug(
            "no_companion_metadata_file_found",
            file=str(file_path),
        )
        return None
