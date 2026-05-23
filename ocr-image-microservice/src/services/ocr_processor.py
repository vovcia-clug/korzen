"""OCR processor using Datalab SDK."""
from typing import Optional, Tuple
from datalab_sdk import DatalabClient, ConvertOptions
from PIL import Image
import os
import tempfile

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Datalab SDK constraints
MAX_WIDTH = 4800
MAX_HEIGHT = 4800


class OCRProcessor:
    """Process images using Datalab SDK OCR."""
    
    def __init__(
        self,
        output_format: str = "markdown",
        mode: str = "accurate",
        paginate: bool = True
    ):
        """
        Initialize OCR processor.
        
        Args:
            output_format: Output format for OCR results (e.g., "markdown")
            mode: OCR processing mode (e.g., "balanced", "fast", "accurate")
            paginate: Whether to paginate the output
        """
        self.output_format = output_format
        self.mode = mode
        self.paginate = paginate
        
        # Initialize Datalab client
        self.client = DatalabClient()
        
        logger.info(
            f"OCRProcessor initialized - Format: {output_format}, "
            f"Mode: {mode}, Paginate: {paginate}"
        )
    
    def _resize_if_needed(self, image_path: str) -> Tuple[str, bool]:
        """
        Resize image if it exceeds maximum dimensions.
        
        Args:
            image_path: Path to the original image
            
        Returns:
            Tuple of (path_to_use, was_resized)
            - path_to_use: Path to the image to use (resized or original)
            - was_resized: Whether the image was resized
        """
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                logger.info(f"Original image dimensions: {width}x{height} pixels")
                
                # Check if resizing is needed
                if width <= MAX_WIDTH and height <= MAX_HEIGHT:
                    logger.info("Image dimensions are within limits, no resizing needed")
                    return image_path, False
                
                # Calculate scale factor to fit within limits while maintaining aspect ratio
                width_scale = MAX_WIDTH / width if width > MAX_WIDTH else 1.0
                height_scale = MAX_HEIGHT / height if height > MAX_HEIGHT else 1.0
                scale_factor = min(width_scale, height_scale)
                
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                
                logger.info(
                    f"Resizing image from {width}x{height} to {new_width}x{new_height} "
                    f"(scale factor: {scale_factor:.4f})"
                )
                
                # Resize the image with high-quality resampling
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save to temporary file
                # Get file extension from original
                _, ext = os.path.splitext(image_path)
                if not ext:
                    ext = '.png'  # Default to PNG if no extension
                
                # Create temporary file
                temp_fd, temp_path = tempfile.mkstemp(suffix=ext, prefix='ocr_resized_')
                os.close(temp_fd)  # Close file descriptor, we'll write with PIL
                
                # Save resized image
                # Preserve format and quality
                save_kwargs = {}
                if img.format:
                    save_kwargs['format'] = img.format
                if img.format in ['JPEG', 'JPG']:
                    save_kwargs['quality'] = 95
                    save_kwargs['optimize'] = True
                elif img.format == 'PNG':
                    save_kwargs['optimize'] = True
                
                resized_img.save(temp_path, **save_kwargs)
                
                logger.info(f"Resized image saved to temporary file: {temp_path}")
                return temp_path, True
                
        except Exception as e:
            logger.error(f"Failed to resize image {image_path}: {e}")
            # Fall back to original image
            return image_path, False
    
    def process_image(self, image_path: str) -> str:
        """
        Process an image file with OCR.
        
        Automatically resizes images that exceed Datalab SDK dimension limits
        while maintaining aspect ratio.
        
        Args:
            image_path: Local path to the image file
        
        Returns:
            OCR result as markdown text
        
        Raises:
            Exception: If OCR processing fails
        """
        temp_file_to_cleanup = None
        
        try:
            logger.info(f"Starting OCR processing for: {image_path}")
            
            # Resize image if needed
            processing_path, was_resized = self._resize_if_needed(image_path)
            
            # Track temporary file for cleanup
            if was_resized:
                temp_file_to_cleanup = processing_path
            
            # Configure OCR options
            options = ConvertOptions(
                output_format=self.output_format,
                mode=self.mode,
                paginate=self.paginate
            )
            
            logger.info(
                f"Calling Datalab SDK with options: format={self.output_format}, "
                f"mode={self.mode}, paginate={self.paginate}"
            )
            
            # Process image with Datalab SDK
            result = self.client.convert(processing_path, options=options)
            
            # DIAGNOSTIC: Log result type and success status
            logger.info(f"Datalab SDK returned result type: {type(result)}")
            if hasattr(result, 'success'):
                logger.info(f"Conversion success status: {result.success}")
                if not result.success and hasattr(result, 'error'):
                    logger.error(f"Conversion error: {result.error}")
            
            # Extract markdown from result
            # ConversionResult has 'markdown' attribute, some other types may have 'text'
            markdown_text = getattr(result, 'markdown', None)
            if not markdown_text:
                markdown_text = getattr(result, 'text', None)
            if not markdown_text:
                if isinstance(result, str):
                    markdown_text = result
                else:
                    # Fallback: convert result to string
                    logger.warning(f"Result object has unexpected format: {type(result)}")
                    markdown_text = str(result)
            
            logger.info(
                f"OCR processing completed - Output length: {len(markdown_text)} chars"
            )
            
            return markdown_text
            
        except Exception as e:
            logger.error(f"OCR processing failed for {image_path}: {e}")
            raise
        
        finally:
            # Clean up temporary resized file if it was created
            if temp_file_to_cleanup and os.path.exists(temp_file_to_cleanup):
                try:
                    os.unlink(temp_file_to_cleanup)
                    logger.info(f"Cleaned up temporary file: {temp_file_to_cleanup}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file_to_cleanup}: {e}")
