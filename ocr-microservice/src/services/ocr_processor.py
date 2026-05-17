"""OCR processor using Datalab SDK."""
from typing import Optional
from datalab_sdk import DatalabClient, ConvertOptions

from ..utils.logger import get_logger

logger = get_logger(__name__)


class OCRProcessor:
    """Process images using Datalab SDK OCR."""
    
    def __init__(
        self,
        output_format: str = "markdown",
        mode: str = "balanced",
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
    
    def process_image(self, image_path: str) -> str:
        """
        Process an image file with OCR.
        
        Args:
            image_path: Local path to the image file
        
        Returns:
            OCR result as markdown text
        
        Raises:
            Exception: If OCR processing fails
        """
        try:
            logger.info(f"Starting OCR processing for: {image_path}")
            
            # Configure OCR options
            options = ConvertOptions(
                output_format=self.output_format,
                mode=self.mode,
                paginate=self.paginate
            )
            
            # Process image with Datalab SDK
            result = self.client.convert(image_path, options=options)
            
            # Extract text from result
            if hasattr(result, 'text'):
                markdown_text = result.text
            elif isinstance(result, str):
                markdown_text = result
            else:
                # Fallback: convert result to string
                markdown_text = str(result)
            
            logger.info(
                f"OCR processing completed - Output length: {len(markdown_text)} chars"
            )
            
            return markdown_text
            
        except Exception as e:
            logger.error(f"OCR processing failed for {image_path}: {e}")
            raise
    
    def save_result(self, markdown_text: str, output_path: str) -> None:
        """
        Save OCR result to a file.
        
        Args:
            markdown_text: OCR result text
            output_path: Path where to save the result
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_text)
            
            logger.info(f"OCR result saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save OCR result to {output_path}: {e}")
            raise
