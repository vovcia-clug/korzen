"""Image detection and validation service.

This module provides multi-layer image validation including extension checks,
MIME type detection, and image header verification.
"""

import hashlib
from pathlib import Path
from typing import Dict, Tuple

import magic
from PIL import Image

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ImageDetector:
    """Validates and detects image files using multiple validation layers."""

    # MIME types for supported image formats
    SUPPORTED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/bmp",
        "image/tiff",
        "image/webp",
        "image/x-ms-bmp",
    }

    def __init__(
        self,
        supported_extensions: list[str],
        min_size_bytes: int = 1024,
        max_size_bytes: int = 104857600,
        strict_validation: bool = True,
    ):
        """Initialize the image detector.
        
        Args:
            supported_extensions: List of allowed file extensions (e.g., ['.jpg', '.png'])
            min_size_bytes: Minimum acceptable file size
            max_size_bytes: Maximum acceptable file size
            strict_validation: Enable image header validation with Pillow
        """
        self.supported_extensions = [ext.lower() for ext in supported_extensions]
        self.min_size_bytes = min_size_bytes
        self.max_size_bytes = max_size_bytes
        self.strict_validation = strict_validation

        logger.info(
            "image_detector_initialized",
            supported_extensions=self.supported_extensions,
            min_size=min_size_bytes,
            max_size=max_size_bytes,
            strict=strict_validation,
        )

    def is_valid_image(self, file_path: Path) -> Tuple[bool, str, Dict]:
        """Validate if a file is a valid image.
        
        Performs multiple validation layers:
        1. Extension check
        2. File size check
        3. MIME type detection
        4. Image header validation (if strict_validation enabled)
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Tuple of (is_valid, reason, metadata)
            - is_valid: Whether the file is a valid image
            - reason: Reason for validation failure (empty if valid)
            - metadata: Dictionary with file metadata
        """
        metadata = {}

        try:
            # Check if file exists
            if not file_path.exists():
                return False, "File does not exist", metadata

            # Layer 1: Extension check
            extension = file_path.suffix.lower()
            if extension not in self.supported_extensions:
                logger.debug(
                    "extension_check_failed",
                    file=str(file_path),
                    extension=extension,
                    supported=self.supported_extensions,
                )
                return False, f"Unsupported extension: {extension}", metadata

            # Layer 2: File size check
            file_size = file_path.stat().st_size
            metadata["file_size_bytes"] = file_size

            if file_size < self.min_size_bytes:
                logger.debug(
                    "size_check_failed_too_small",
                    file=str(file_path),
                    size=file_size,
                    min_size=self.min_size_bytes,
                )
                return False, f"File too small: {file_size} bytes", metadata

            if file_size > self.max_size_bytes:
                logger.debug(
                    "size_check_failed_too_large",
                    file=str(file_path),
                    size=file_size,
                    max_size=self.max_size_bytes,
                )
                return False, f"File too large: {file_size} bytes", metadata

            # Layer 3: MIME type detection
            mime_type = magic.from_file(str(file_path), mime=True)
            metadata["content_type"] = mime_type

            if mime_type not in self.SUPPORTED_MIME_TYPES:
                logger.debug(
                    "mime_check_failed",
                    file=str(file_path),
                    mime_type=mime_type,
                    supported=list(self.SUPPORTED_MIME_TYPES),
                )
                return False, f"Unsupported MIME type: {mime_type}", metadata

            # Layer 4: Image header validation (strict mode)
            if self.strict_validation:
                try:
                    with Image.open(file_path) as img:
                        # Verify image can be loaded
                        img.verify()

                    # Open again to get dimensions (verify() closes the image)
                    with Image.open(file_path) as img:
                        metadata["image_dimensions"] = {
                            "width": img.width,
                            "height": img.height,
                        }
                        metadata["image_format"] = img.format.lower() if img.format else None
                        metadata["image_mode"] = img.mode

                except Exception as e:
                    logger.warning(
                        "image_header_validation_failed",
                        file=str(file_path),
                        error=str(e),
                    )
                    return False, f"Corrupt or invalid image: {str(e)}", metadata

            # Calculate file hash for deduplication
            metadata["file_hash"] = self._calculate_file_hash(file_path)

            logger.info(
                "image_validated",
                file=str(file_path),
                size=file_size,
                mime_type=mime_type,
                dimensions=metadata.get("image_dimensions"),
            )

            return True, "", metadata

        except Exception as e:
            logger.error(
                "image_validation_error",
                file=str(file_path),
                error=str(e),
                exc_info=True,
            )
            return False, f"Validation error: {str(e)}", metadata

    def _calculate_file_hash(self, file_path: Path, algorithm: str = "sha256") -> Dict[str, str]:
        """Calculate file hash for deduplication.
        
        Args:
            file_path: Path to the file
            algorithm: Hash algorithm (default: sha256)
            
        Returns:
            Dictionary with algorithm and hash value
        """
        try:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)

            return {
                "algorithm": algorithm,
                "value": hash_obj.hexdigest(),
            }
        except Exception as e:
            logger.warning(
                "file_hash_calculation_failed",
                file=str(file_path),
                error=str(e),
            )
            return {"algorithm": algorithm, "value": ""}

    def should_process_file(self, file_path: Path) -> bool:
        """Quick check if file should be processed (extension-based filter).
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file extension is supported
        """
        extension = file_path.suffix.lower()
        return extension in self.supported_extensions
