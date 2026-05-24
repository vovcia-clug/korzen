"""JSON metadata loader for loading companion metadata files from S3."""
import json
import re
from typing import Dict, Optional
from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MetadataJsonLoader:
    """Load and parse JSON metadata files from S3."""
    
    def __init__(self):
        """Initialize metadata JSON loader."""
        logger.info("MetadataJsonLoader initialized")
    
    def load_from_s3(self, s3_handler, s3_uri: str) -> Optional[Dict]:
        """
        Load JSON metadata file from S3 for a given image URI.
        
        Args:
            s3_handler: S3Handler instance
            s3_uri: S3 URI of the image file
        
        Returns:
            Dictionary with parsed JSON metadata, or None if not found
        """
        try:
            # Generate JSON S3 URI by replacing image extension with .json
            json_s3_uri = self._get_json_uri(s3_uri)
            
            logger.info(f"Looking for JSON metadata at: {json_s3_uri}")
            
            # Download JSON file from S3
            local_json_path = s3_handler.download_json(json_s3_uri)
            
            if not local_json_path:
                logger.info(f"No JSON metadata file found for: {s3_uri}")
                return None
            
            # Parse JSON file
            metadata = self._parse_json_file(local_json_path)
            
            # Cleanup local file
            s3_handler.cleanup_local_file(local_json_path)
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Failed to load JSON metadata for {s3_uri}: {e}")
            return None
    
    def _get_json_uri(self, s3_uri: str) -> str:
        """
        Convert image S3 URI to JSON metadata URI.
        
        Args:
            s3_uri: S3 URI of image file (e.g., s3://bucket/path/image.jpg)
        
        Returns:
            S3 URI of JSON file (e.g., s3://bucket/path/image.json)
        """
        # Simple string replacement to preserve S3 URI format
        # Path() doesn't work well with s3:// URIs
        if s3_uri.endswith('.jpg') or s3_uri.endswith('.jpeg'):
            json_uri = s3_uri.rsplit('.', 1)[0] + '.json'
        elif s3_uri.endswith('.png'):
            json_uri = s3_uri.rsplit('.', 1)[0] + '.json'
        elif s3_uri.endswith('.tif') or s3_uri.endswith('.tiff'):
            json_uri = s3_uri.rsplit('.', 1)[0] + '.json'
        else:
            # Generic fallback
            json_uri = s3_uri.rsplit('.', 1)[0] + '.json'
        
        return json_uri
    
    def _parse_json_file(self, json_file_path: str) -> Optional[Dict]:
        """
        Parse JSON metadata file.
        
        Args:
            json_file_path: Local path to JSON file
        
        Returns:
            Dictionary with parsed metadata, or None if parsing fails
        """
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Successfully parsed JSON metadata: {list(data.keys())}")
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON file {json_file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading JSON file {json_file_path}: {e}")
            return None
    
    def extract_skanoteka_metadata(self, json_data: Dict) -> Optional[Dict]:
        """
        Extract Skanoteka-specific metadata from JSON data.
        
        Expected JSON structure from scraper:
        {
            "place": "Bolechów",
            "unit": "4500 M-1874-1937-Bolechów",
            "years": "1874-1937",
            "page": "301.jpg (301 z 303)",
            "collection_id": "1784",
            "powiat": "krakowski"
        }
        
        Args:
            json_data: Parsed JSON data
        
        Returns:
            Dictionary with Skanoteka metadata, or None if not found
        """
        if not json_data:
            return None
        
        # Check if this is Skanoteka metadata
        skanoteka_fields = ['place', 'unit', 'years', 'page']
        has_skanoteka = any(field in json_data for field in skanoteka_fields)
        
        if not has_skanoteka:
            logger.debug("JSON data does not contain Skanoteka fields")
            return None
        
        skanoteka_metadata = {}
        
        # Extract collection_id and powiat first (for composite document_id)
        collection_id = json_data.get('collection_id')
        powiat = json_data.get('powiat')
        
        if collection_id:
            skanoteka_metadata['collection_id'] = collection_id
        if powiat:
            skanoteka_metadata['powiat'] = powiat
        
        # Extract basic fields
        if 'place' in json_data:
            skanoteka_metadata['place'] = json_data['place']
        
        if 'unit' in json_data:
            skanoteka_metadata['unit'] = json_data['unit']
            # Extract document_id from unit with collection context
            document_id = self._extract_document_id_from_unit(
                json_data['unit'],
                collection_id=collection_id
            )
            if document_id:
                skanoteka_metadata['document_id'] = document_id
                # Also store unit_number separately
                unit_number = self._extract_unit_number(json_data['unit'])
                if unit_number:
                    skanoteka_metadata['unit_number'] = unit_number
        
        if 'years' in json_data:
            skanoteka_metadata['years'] = json_data['years']
        
        if 'page' in json_data:
            skanoteka_metadata['page'] = json_data['page']
            # Extract page number from page field
            page_number = self._extract_page_number_from_page_field(json_data['page'])
            if page_number is not None:
                skanoteka_metadata['page_number'] = page_number
            
            # Extract total pages from page field
            total_pages = self._extract_total_pages_from_page_field(json_data['page'])
            if total_pages is not None:
                skanoteka_metadata['total_pages'] = total_pages
        
        logger.info(f"Extracted Skanoteka metadata: {skanoteka_metadata}")
        return skanoteka_metadata
    
    def _extract_unit_number(self, unit: str) -> Optional[str]:
        """
        Extract unit number from unit string.
        
        Examples:
            "4500 M-1874-1937-Bolechów" -> "4500"
            "3500 U-1750-1777" -> "3500"
        
        Args:
            unit: Unit string from Skanoteka
        
        Returns:
            Unit number or None
        """
        try:
            # Extract leading number from unit string
            match = re.match(r'^(\d+)', unit.strip())
            if match:
                unit_number = match.group(1)
                logger.debug(f"Extracted unit_number '{unit_number}' from unit '{unit}'")
                return unit_number
        except Exception as e:
            logger.warning(f"Failed to extract unit_number from unit '{unit}': {e}")
        
        return None
    
    def _extract_document_id_from_unit(self, unit: str, collection_id: Optional[str] = None) -> Optional[str]:
        """
        Extract document ID from unit string with collection context.
        
        When collection_id is provided, creates a composite document_id to prevent
        collisions when scanning powiaty with multiple collections.
        
        Examples:
            ("4500 M-1874-1937-Bolechów", "1784") -> "1784-4500"
            ("3500 U-1750-1777", "1885") -> "1885-3500"
            ("4500 M-1874-1937-Bolechów", None) -> "4500"
        
        Args:
            unit: Unit string from Skanoteka
            collection_id: Optional collection ID for composite document_id
        
        Returns:
            Document ID (composite or unit number) or None
        """
        try:
            # Extract leading number from unit string
            match = re.match(r'^(\d+)', unit.strip())
            if match:
                unit_number = match.group(1)
                
                # Create composite document_id if collection_id is available
                if collection_id:
                    document_id = f"{collection_id}-{unit_number}"
                    logger.debug(
                        f"Extracted composite document_id '{document_id}' "
                        f"from unit '{unit}' and collection_id '{collection_id}'"
                    )
                else:
                    document_id = unit_number
                    logger.debug(f"Extracted document_id '{document_id}' from unit '{unit}'")
                
                return document_id
        except Exception as e:
            logger.warning(f"Failed to extract document_id from unit '{unit}': {e}")
        
        return None
    
    def _extract_page_number_from_page_field(self, page: str) -> Optional[int]:
        """
        Extract page number from page field.
        
        Examples:
            "301.jpg (301 z 303)" -> 301
            "005.jpg (5 z 175)" -> 5
            "page-042.jpg (42 z 100)" -> 42
        
        Args:
            page: Page string from Skanoteka
        
        Returns:
            Page number or None
        """
        try:
            # Pattern: "filename (X z Y)" where X is the page number
            match = re.search(r'\((\d+)\s+z\s+\d+\)', page)
            if match:
                page_number = int(match.group(1))
                logger.debug(f"Extracted page_number {page_number} from page '{page}'")
                return page_number
            
            # Fallback: try to extract number from filename
            match = re.search(r'(\d+)\.', page)
            if match:
                page_number = int(match.group(1))
                logger.debug(f"Extracted page_number {page_number} from filename in '{page}'")
                return page_number
                
        except Exception as e:
            logger.warning(f"Failed to extract page_number from page '{page}': {e}")
        
        return None
    
    def _extract_total_pages_from_page_field(self, page: str) -> Optional[int]:
        """
        Extract total pages from page field.
        
        Examples:
            "301.jpg (301 z 303)" -> 303
            "005.jpg (5 z 175)" -> 175
        
        Args:
            page: Page string from Skanoteka
        
        Returns:
            Total pages or None
        """
        try:
            # Pattern: "filename (X z Y)" where Y is the total pages
            match = re.search(r'\(\d+\s+z\s+(\d+)\)', page)
            if match:
                total_pages = int(match.group(1))
                logger.debug(f"Extracted total_pages {total_pages} from page '{page}'")
                return total_pages
                
        except Exception as e:
            logger.warning(f"Failed to extract total_pages from page '{page}': {e}")
        
        return None
