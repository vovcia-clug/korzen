"""S3 handler for downloading and uploading files."""
import os
from typing import Optional
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class S3Handler:
    """Handle S3 download and upload operations."""
    
    def __init__(
        self,
        aws_config: dict,
        input_bucket: str,
        output_bucket: str,
        output_prefix: str = "ocr-results/",
        temp_dir: str = "/tmp/ocr-processing"
    ):
        """
        Initialize S3 handler.
        
        Args:
            aws_config: AWS configuration dictionary for boto3
            input_bucket: S3 bucket name for input images
            output_bucket: S3 bucket name for output results
            output_prefix: Prefix for output files in S3
            temp_dir: Local temporary directory for file processing
        """
        self.input_bucket = input_bucket
        self.output_bucket = output_bucket
        self.output_prefix = output_prefix
        self.temp_dir = temp_dir
        
        # Create S3 client
        self.s3_client = boto3.client("s3", **aws_config)
        
        # Ensure temp directory exists
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"S3Handler initialized - Input: {input_bucket}, "
            f"Output: {output_bucket}/{output_prefix}"
        )
    
    def download_image(self, s3_key: str) -> str:
        """
        Download an image from S3 to local temporary storage.
        
        Args:
            s3_key: S3 object key (path within bucket)
        
        Returns:
            Local file path of downloaded image
        
        Raises:
            ClientError: If S3 download fails
        """
        # Generate local file path
        filename = os.path.basename(s3_key)
        local_path = os.path.join(self.temp_dir, filename)
        
        try:
            logger.info(f"Downloading s3://{self.input_bucket}/{s3_key} to {local_path}")
            
            self.s3_client.download_file(
                Bucket=self.input_bucket,
                Key=s3_key,
                Filename=local_path
            )
            
            logger.info(f"Successfully downloaded {s3_key}")
            return local_path
            
        except ClientError as e:
            logger.error(f"Failed to download {s3_key}: {e}")
            raise
    
    def upload_result(
        self,
        local_path: str,
        original_s3_key: str,
        content_type: str = "text/markdown"
    ) -> str:
        """
        Upload OCR result to S3.
        
        Args:
            local_path: Local file path of the result
            original_s3_key: Original S3 key (used to generate output key)
            content_type: MIME type of the result file
        
        Returns:
            S3 URI of uploaded result (s3://bucket/key)
        
        Raises:
            ClientError: If S3 upload fails
        """
        # Generate output S3 key
        original_filename = os.path.basename(original_s3_key)
        base_name = os.path.splitext(original_filename)[0]
        output_key = f"{self.output_prefix}{base_name}.md"
        
        try:
            logger.info(
                f"Uploading {local_path} to s3://{self.output_bucket}/{output_key}"
            )
            
            self.s3_client.upload_file(
                Filename=local_path,
                Bucket=self.output_bucket,
                Key=output_key,
                ExtraArgs={"ContentType": content_type}
            )
            
            s3_uri = f"s3://{self.output_bucket}/{output_key}"
            logger.info(f"Successfully uploaded result to {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            logger.error(f"Failed to upload result: {e}")
            raise
    
    def parse_s3_uri(self, s3_uri: str) -> tuple[str, str]:
        """
        Parse S3 URI into bucket and key components.
        
        Args:
            s3_uri: S3 URI in format s3://bucket/key
        
        Returns:
            Tuple of (bucket, key)
        
        Raises:
            ValueError: If URI format is invalid
        """
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        # Remove s3:// prefix and split
        path = s3_uri[5:]
        parts = path.split("/", 1)
        
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        bucket, key = parts
        return bucket, key
    
    def cleanup_local_file(self, file_path: str) -> None:
        """
        Remove a local file after processing.
        
        Args:
            file_path: Path to file to remove
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up local file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}")
