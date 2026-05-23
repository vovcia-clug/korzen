"""S3 handler for downloading and uploading GEDCOM files."""
import os
from typing import Optional
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class S3Handler:
    """Handle S3 download and upload operations for GEDCOM files."""
    
    def __init__(
        self,
        aws_config: dict,
        output_bucket: str,
        output_prefix: str = "gedcom-files/",
        temp_dir: str = "/tmp/gedcom-upload"
    ):
        """
        Initialize S3 handler.
        
        Args:
            aws_config: AWS configuration dictionary for boto3
            output_bucket: S3 bucket name for output GEDCOM files
            output_prefix: Prefix for output files in S3
            temp_dir: Local temporary directory for file processing
        """
        self.output_bucket = output_bucket
        self.output_prefix = output_prefix
        self.temp_dir = temp_dir
        
        # Create S3 client
        self.s3_client = boto3.client("s3", **aws_config)
        
        # Ensure temp directory exists
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"S3Handler initialized - Output: {output_bucket}/{output_prefix}"
        )
    
    def download_gedcom(self, s3_uri: str) -> str:
        """
        Download a GEDCOM file from S3 to local temporary storage.
        
        Args:
            s3_uri: S3 URI (s3://bucket/key)
        
        Returns:
            Local file path of downloaded GEDCOM
        
        Raises:
            ClientError: If S3 download fails
            ValueError: If S3 URI is invalid
        """
        # Parse S3 URI
        bucket, key = self.parse_s3_uri(s3_uri)
        
        # Generate local file path
        filename = os.path.basename(key)
        local_path = os.path.join(self.temp_dir, filename)
        
        try:
            logger.info(f"Downloading {s3_uri} to {local_path}")
            
            self.s3_client.download_file(
                Bucket=bucket,
                Key=key,
                Filename=local_path
            )
            
            logger.info(f"Successfully downloaded {filename}")
            return local_path
            
        except ClientError as e:
            logger.error(f"Failed to download {s3_uri}: {e}")
            raise
    
    def upload_gedcom(
        self,
        gedcom_content: str,
        document_id: str,
        filename: Optional[str] = None
    ) -> str:
        """
        Upload GEDCOM content to S3.
        
        Args:
            gedcom_content: GEDCOM file content as string
            document_id: Document ID for organizing files
            filename: Optional filename (defaults to document_id.ged)
        
        Returns:
            S3 URI of uploaded file
        
        Raises:
            ClientError: If S3 upload fails
        """
        # Generate output S3 key
        if filename is None:
            filename = f"{document_id}.ged"
        
        output_key = f"{self.output_prefix}{document_id}/{filename}"
        
        try:
            logger.info(
                f"Uploading GEDCOM ({len(gedcom_content)} bytes) to "
                f"s3://{self.output_bucket}/{output_key}"
            )
            
            # Upload string content directly
            self.s3_client.put_object(
                Bucket=self.output_bucket,
                Key=output_key,
                Body=gedcom_content.encode('utf-8'),
                ContentType='text/x-gedcom'
            )
            
            s3_uri = f"s3://{self.output_bucket}/{output_key}"
            logger.info(f"Successfully uploaded GEDCOM to {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            logger.error(f"Failed to upload GEDCOM: {e}")
            raise
    
    def parse_s3_uri(self, s3_uri: str) -> tuple[str, str]:
        """
        Parse S3 URI into bucket and key components.
        
        Args:
            s3_uri: S3 URI in format s3://bucket/key
        
        Returns:
            Tuple of (bucket_name, object_key)
        
        Raises:
            ValueError: If URI format is invalid
        """
        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        # Remove s3:// prefix
        path = s3_uri[5:]
        
        # Split into bucket and key
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        bucket = parts[0]
        key = parts[1]
        
        return bucket, key
    
    def cleanup_temp_file(self, local_path: str) -> None:
        """
        Clean up temporary file after processing.
        
        Args:
            local_path: Path to temporary file
        """
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
                logger.debug(f"Cleaned up temporary file: {local_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {local_path}: {e}")
