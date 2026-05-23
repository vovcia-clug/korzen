"""JSON metadata file handler.

This module handles detection and management of companion JSON metadata files
that should be uploaded alongside image files.
"""

from pathlib import Path
from typing import Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


class MetadataHandler:
    """Handles companion JSON metadata files."""

    def __init__(self):
        """Initialize the metadata handler."""
        logger.info("metadata_handler_initialized")

    def find_companion_json(self, file_path: Path) -> Optional[Path]:
        """Find companion JSON file for an image file.
        
        This method looks for a companion .json file that should be uploaded
        alongside the image file.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Path to companion JSON file if found, None otherwise
        """
        # Check for companion .json file
        json_file = file_path.with_suffix(".json")
        if json_file.exists() and json_file.is_file():
            logger.info(
                "found_companion_json_file",
                image_file=str(file_path),
                json_file=str(json_file),
            )
            return json_file
        
        logger.debug(
            "no_companion_json_file_found",
            image_file=str(file_path),
        )
        return None
