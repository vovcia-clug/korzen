"""Metadata extractor for extracting document metadata from S3 paths and tags."""
import re
from typing import Dict, Optional, Tuple
from PIL import Image

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MetadataExtractor:
    """Extract metadata from S3 URIs and object tags."""
    
    def __init__(self):
        """Initialize metadata extractor."""
        logger.info("MetadataExtractor initialized")
    
    def extract_from_s3_path(self, s3_uri: str) -> Dict[str, any]:
        """
        Extract document_id and page_number from S3 URI path patterns.
        
        Supported patterns:
        - s3://bucket/documents/{document_id}/page-{page_number}.jpg
        - s3://bucket/documents/{document_id}/{page_number}.jpg
        - s3://bucket/{document_id}/page-{page_number}.jpg
        - s3://bucket/{document_id}/{filename}
        
        Args:
            s3_uri: S3 URI (e.g., s3://bucket/documents/book-123/page-005.jpg)
        
        Returns:
            Dictionary with extracted metadata (document_id, page_number, filename)
        """
        metadata = {}
        
        try:
            # Extract the path part after bucket
            # Pattern: s3://bucket/path/to/file
            match = re.match(r's3://[^/]+/(.+)', s3_uri)
            if not match:
                logger.warning(f"Could not parse S3 URI: {s3_uri}")
                return metadata
            
            path = match.group(1)
            parts = path.split('/')
            filename = parts[-1]
            
            metadata['filename'] = filename
            
            # Try to extract page number from filename
            # Patterns: page-005.jpg, page_005.jpg, 005.jpg, p005.jpg
            page_patterns = [
                r'page[-_](\d+)',  # page-005 or page_005
                r'p(\d+)',         # p005
                r'^(\d+)\.',       # 005.jpg (number at start)
            ]
            
            for pattern in page_patterns:
                page_match = re.search(pattern, filename, re.IGNORECASE)
                if page_match:
                    page_number = int(page_match.group(1))
                    metadata['page_number'] = page_number
                    logger.info(f"Extracted page_number={page_number} from filename: {filename}")
                    break
            
            # Try to extract document_id from path
            # Look for a directory name before the filename
            if len(parts) >= 2:
                # Use the parent directory as document_id
                document_id = parts[-2]
                metadata['document_id'] = document_id
                logger.info(f"Extracted document_id={document_id} from path")
            
            # If path has more structure, try to find a better document_id
            # Pattern: documents/{document_id}/... or books/{document_id}/...
            for i, part in enumerate(parts[:-1]):
                if part in ['documents', 'books', 'records', 'images']:
                    if i + 1 < len(parts):
                        document_id = parts[i + 1]
                        metadata['document_id'] = document_id
                        logger.info(f"Extracted document_id={document_id} from structured path")
                        break
            
        except Exception as e:
            logger.error(f"Error extracting metadata from S3 path: {e}")
        
        return metadata
    
    def extract_from_tags(self, tags: Dict[str, str]) -> Dict[str, any]:
        """
        Extract metadata from S3 object tags.
        
        Expected tags:
        - document_id: Unique identifier for the document/book
        - page_number: Page number within the document
        - total_pages: Total number of pages in the document
        - document_title: Title of the document
        - date_range: Date range covered by the document (e.g., "1820-1850")
        - location: Location/parish name
        - record_type: Type of records (e.g., "baptism", "marriage", "death")
        - language: Language of the document (e.g., "latin", "polish")
        - source: Source type (e.g., "parish_register")
        
        Args:
            tags: Dictionary of S3 object tags
        
        Returns:
            Dictionary with extracted and typed metadata
        """
        metadata = {}
        
        try:
            # Extract string fields
            string_fields = [
                'document_id',
                'document_title',
                'date_range',
                'location',
                'record_type',
                'language',
                'source'
            ]
            
            for field in string_fields:
                if field in tags:
                    metadata[field] = tags[field]
                    logger.info(f"Extracted {field}={tags[field]} from tags")
            
            # Extract integer fields
            if 'page_number' in tags:
                try:
                    metadata['page_number'] = int(tags['page_number'])
                    logger.info(f"Extracted page_number={metadata['page_number']} from tags")
                except ValueError:
                    logger.warning(f"Invalid page_number in tags: {tags['page_number']}")
            
            if 'total_pages' in tags:
                try:
                    metadata['total_pages'] = int(tags['total_pages'])
                    logger.info(f"Extracted total_pages={metadata['total_pages']} from tags")
                except ValueError:
                    logger.warning(f"Invalid total_pages in tags: {tags['total_pages']}")
            
        except Exception as e:
            logger.error(f"Error extracting metadata from tags: {e}")
        
        return metadata
    
    def get_image_dimensions(self, image_path: str) -> Optional[Tuple[int, int]]:
        """
        Get image dimensions (width, height).
        
        Args:
            image_path: Local path to image file
        
        Returns:
            Tuple of (width, height) or None if failed
        """
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                logger.info(f"Image dimensions: {width}x{height}")
                return width, height
        except Exception as e:
            logger.error(f"Failed to get image dimensions: {e}")
            return None
    
    def merge_metadata(
        self,
        path_metadata: Dict[str, any],
        tag_metadata: Dict[str, any]
    ) -> Dict[str, any]:
        """
        Merge metadata from path and tags, with tags taking precedence.
        
        Args:
            path_metadata: Metadata extracted from S3 path
            tag_metadata: Metadata extracted from S3 tags
        
        Returns:
            Merged metadata dictionary
        """
        # Start with path metadata
        merged = path_metadata.copy()
        
        # Override with tag metadata (tags are more authoritative)
        merged.update(tag_metadata)
        
        logger.info(f"Merged metadata: {merged}")
        return merged
    
    def extract_all(
        self,
        s3_uri: str,
        tags: Dict[str, str],
        image_path: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Extract all available metadata from S3 URI, tags, and image.
        
        Args:
            s3_uri: S3 URI of the image
            tags: S3 object tags
            image_path: Optional local path to image file
        
        Returns:
            Complete metadata dictionary
        """
        # Extract from path
        path_metadata = self.extract_from_s3_path(s3_uri)
        
        # Extract from tags
        tag_metadata = self.extract_from_tags(tags)
        
        # Merge metadata (tags take precedence)
        metadata = self.merge_metadata(path_metadata, tag_metadata)
        
        # Add image dimensions if available
        if image_path:
            dimensions = self.get_image_dimensions(image_path)
            if dimensions:
                metadata['image_width'] = dimensions[0]
                metadata['image_height'] = dimensions[1]
        
        logger.info(f"Extracted complete metadata: {list(metadata.keys())}")
        return metadata
