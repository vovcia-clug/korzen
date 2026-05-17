"""S3 handler for downloading and uploading files."""
import os
import re
from typing import Optional
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse

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
    
    def upload_file_result(
        self,
        local_path: str,
        original_s3_key: str,
        content_type: str = "text/markdown"
    ) -> str:
        """
        Upload OCR result file to S3 (legacy method for file-based uploads).
        
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
    
    def upload_result(
        self,
        content: str,
        s3_uri: str,
        output_prefix: str,
        file_extension: str = ".md"
    ) -> str:
        """
        Upload processing result to S3 with specified extension.
        
        Args:
            content: Text content to upload
            s3_uri: Original S3 URI (used to derive basename)
            output_prefix: S3 prefix for output (e.g., "ocr-results/", "gedcom-files/")
            file_extension: File extension including dot (e.g., ".md", ".json", ".ged")
        
        Returns:
            S3 URI of uploaded file
        
        Raises:
            ClientError: If S3 upload fails
        """
        # Parse S3 URI to get the original key
        try:
            _, original_key = self.parse_s3_uri(s3_uri)
        except ValueError as e:
            logger.error(f"Failed to parse S3 URI: {e}")
            raise
        
        # Generate output S3 key
        original_filename = os.path.basename(original_key)
        base_name = os.path.splitext(original_filename)[0]
        output_key = f"{output_prefix}{base_name}{file_extension}"
        
        # Determine content type based on extension
        content_type_map = {
            ".md": "text/markdown",
            ".json": "application/json",
            ".ged": "text/x-gedcom",
            ".txt": "text/plain"
        }
        content_type = content_type_map.get(file_extension, "text/plain")
        
        try:
            logger.info(
                f"Uploading {len(content)} bytes to s3://{self.output_bucket}/{output_key}"
            )
            
            # Upload string content directly
            self.s3_client.put_object(
                Bucket=self.output_bucket,
                Key=output_key,
                Body=content.encode('utf-8'),
                ContentType=content_type
            )
            
            s3_uri_result = f"s3://{self.output_bucket}/{output_key}"
            logger.info(f"Successfully uploaded result to {s3_uri_result}")
            return s3_uri_result
            
        except ClientError as e:
            logger.error(f"Failed to upload result: {e}")
            raise
    
    def parse_s3_uri(self, s3_uri: str) -> tuple[str, str]:
        """
        Parse S3 URI into bucket and key components.
        
        Supports multiple formats:
        - S3 URI: s3://bucket/key
        - S3 ARN: arn:aws:s3:::bucket/key or arn:aws:s3:region:account:accesspoint/...
        - HTTPS URL: https://bucket.s3.region.amazonaws.com/key
        - HTTPS URL (path-style): https://s3.region.amazonaws.com/bucket/key
        
        Args:
            s3_uri: S3 URI, ARN, or HTTPS URL
        
        Returns:
            Tuple of (bucket, key)
        
        Raises:
            ValueError: If URI format is invalid
        """
        # DIAGNOSTIC: Log the URI format being parsed
        logger.info(f"DIAGNOSTIC - Attempting to parse S3 URI: {s3_uri}")
        logger.info(f"DIAGNOSTIC - URI length: {len(s3_uri)}, Type: {type(s3_uri)}")
        
        # Handle S3 ARN format: arn:aws:s3:::bucket-name/key or arn:aws:s3:::bucket-name
        if s3_uri.startswith("arn:aws:s3"):
            logger.info("DIAGNOSTIC - Detected ARN format")
            
            # Parse the ARN
            # Standard S3 ARN for objects: arn:aws:s3:::bucket-name/key-name
            # Note: S3 object ARNs have three colons after s3 (no region/account)
            arn_match = re.match(r'^arn:aws:s3:::(.+?)(?:/(.+))?$', s3_uri)
            
            if arn_match:
                bucket = arn_match.group(1)
                key = arn_match.group(2)
                
                if not key:
                    logger.error(f"DIAGNOSTIC - ARN contains bucket but no key: {s3_uri}")
                    raise ValueError(f"S3 ARN missing object key: {s3_uri}")
                
                logger.info(f"DIAGNOSTIC - Parsed S3 ARN -> bucket: {bucket}, key: {key}")
                return bucket, key
            else:
                # Try to parse access point ARN (more complex format)
                # arn:aws:s3:region:account-id:accesspoint/accesspoint-name
                # These require special handling and may not work with simple download_file
                logger.error(f"DIAGNOSTIC - Unsupported or malformed ARN format: {s3_uri}")
                raise ValueError(
                    f"Unsupported S3 ARN format. Expected 'arn:aws:s3:::bucket/key' but got: {s3_uri}"
                )
        
        # Handle s3:// format
        elif s3_uri.startswith("s3://"):
            logger.info("DIAGNOSTIC - Detected s3:// format")
            # Remove s3:// prefix and split
            path = s3_uri[5:]
            parts = path.split("/", 1)
            
            if len(parts) != 2:
                raise ValueError(f"Invalid S3 URI format: {s3_uri}")
            
            bucket, key = parts
            logger.info(f"DIAGNOSTIC - Parsed s3:// URI -> bucket: {bucket}, key: {key}")
            return bucket, key
        
        # Handle https:// format
        elif s3_uri.startswith("https://"):
            logger.info("DIAGNOSTIC - Detected https:// format")
            parsed = urlparse(s3_uri)
            hostname = parsed.hostname
            path = parsed.path.lstrip('/')
            
            if not hostname or not path:
                raise ValueError(f"Invalid HTTPS S3 URL format: {s3_uri}")
            
            # Virtual-hosted-style URL: https://bucket.s3.region.amazonaws.com/key
            # Pattern: bucket-name.s3.region.amazonaws.com or bucket-name.s3.amazonaws.com
            virtual_hosted_match = re.match(
                r'^(.+?)\.s3[.-]([a-z0-9-]+)?\.amazonaws\.com$',
                hostname
            )
            
            if virtual_hosted_match:
                bucket = virtual_hosted_match.group(1)
                key = path
                logger.info(
                    f"DIAGNOSTIC - Parsed virtual-hosted HTTPS URL -> "
                    f"bucket: {bucket}, key: {key}"
                )
                return bucket, key
            
            # Path-style URL: https://s3.region.amazonaws.com/bucket/key
            # Pattern: s3.region.amazonaws.com or s3.amazonaws.com
            path_style_match = re.match(
                r'^s3[.-]([a-z0-9-]+)?\.amazonaws\.com$',
                hostname
            )
            
            if path_style_match:
                # First part of path is bucket, rest is key
                path_parts = path.split('/', 1)
                if len(path_parts) != 2:
                    raise ValueError(
                        f"Invalid path-style S3 URL format: {s3_uri}"
                    )
                bucket, key = path_parts
                logger.info(
                    f"DIAGNOSTIC - Parsed path-style HTTPS URL -> "
                    f"bucket: {bucket}, key: {key}"
                )
                return bucket, key
            
            # If we get here, the hostname doesn't match S3 patterns
            logger.error(
                f"DIAGNOSTIC - HTTPS URL hostname '{hostname}' does not match "
                f"known S3 URL patterns"
            )
            raise ValueError(
                f"Invalid S3 HTTPS URL format (unknown hostname pattern): {s3_uri}"
            )
        
        else:
            logger.error(
                f"DIAGNOSTIC - URI does not start with 's3://', 'arn:aws:s3', or 'https://': {s3_uri[:50]}"
            )
            raise ValueError(
                f"Invalid S3 URI format. Must start with 's3://', 'arn:aws:s3', or 'https://': {s3_uri}"
            )
    
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
