"""S3 upload service.

This module handles uploading image files to AWS S3 with multipart support,
metadata attachment, and retry logic.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..utils.logger import get_logger

logger = get_logger(__name__)


class S3Uploader:
    """Handles uploading files to AWS S3 with retry logic."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "uploads/",
        region: str = "us-east-1",
        server_side_encryption: str = "AES256",
        storage_class: str = "STANDARD",
        multipart_threshold_mb: int = 5,
        max_retries: int = 3,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """Initialize the S3 uploader.
        
        Args:
            bucket: Target S3 bucket name
            prefix: Object key prefix (default: "uploads/")
            region: AWS region
            server_side_encryption: Encryption algorithm (AES256, aws:kms)
            storage_class: S3 storage class
            multipart_threshold_mb: Size threshold for multipart uploads
            max_retries: Maximum retry attempts
            aws_access_key_id: AWS access key (optional if using IAM roles)
            aws_secret_access_key: AWS secret key (optional if using IAM roles)
        """
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self.server_side_encryption = server_side_encryption
        self.storage_class = storage_class
        self.multipart_threshold_bytes = multipart_threshold_mb * 1024 * 1024
        self.max_retries = max_retries

        # Configure boto3 client
        boto_config = BotoConfig(
            region_name=region,
            retries={"max_attempts": max_retries, "mode": "adaptive"},
        )

        # Create S3 client
        session_kwargs = {}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key

        session = boto3.Session(**session_kwargs)
        self.s3_client = session.client("s3", config=boto_config)

        logger.info(
            "s3_uploader_initialized",
            bucket=bucket,
            prefix=self.prefix,
            region=region,
            multipart_threshold_mb=multipart_threshold_mb,
        )

    def generate_s3_key(self, file_path: Path, preserve_structure: bool = False) -> str:
        """Generate S3 object key for file.
        
        Args:
            file_path: Path to the file
            preserve_structure: Preserve directory structure in key
            
        Returns:
            S3 object key
        """
        # Generate timestamp-based path
        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")

        # Generate unique filename (UUID only, no original filename)
        unique_id = str(uuid.uuid4())
        file_extension = file_path.suffix  # Preserve file extension
        unique_filename = f"{unique_id}{file_extension}"

        # Construct full key
        if preserve_structure:
            # Include parent directory structure
            relative_path = file_path.parent.name
            s3_key = f"{self.prefix}{date_path}/{relative_path}/{unique_filename}"
        else:
            s3_key = f"{self.prefix}{date_path}/{unique_filename}"

        return s3_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((ClientError, ConnectionError)),
        reraise=True,
    )
    def upload_file(
        self,
        file_path: Path,
        metadata: Optional[Dict] = None,
        s3_key: Optional[str] = None,
    ) -> str:
        """Upload file to S3 with retry logic.
        
        Args:
            file_path: Path to file to upload
            metadata: Additional metadata to attach
            s3_key: Custom S3 key (generated if not provided)
            
        Returns:
            S3 URI of uploaded object (s3://bucket/key)
            
        Raises:
            ClientError: If upload fails after retries
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Generate S3 key if not provided
        if s3_key is None:
            s3_key = self.generate_s3_key(file_path)

        # Get file size
        file_size = file_path.stat().st_size

        # Prepare metadata
        s3_metadata = self._prepare_metadata(file_path, metadata or {})

        logger.info(
            "upload_started",
            file=str(file_path),
            s3_key=s3_key,
            file_size=file_size,
            multipart=file_size >= self.multipart_threshold_bytes,
        )

        try:
            # Determine content type
            content_type = metadata.get("content_type", "application/octet-stream") if metadata else "application/octet-stream"

            # Prepare upload parameters
            extra_args = {
                "Metadata": s3_metadata,
                "ContentType": content_type,
                "ServerSideEncryption": self.server_side_encryption,
                "StorageClass": self.storage_class,
            }

            # Use multipart upload for large files
            if file_size >= self.multipart_threshold_bytes:
                self._upload_with_multipart(file_path, s3_key, extra_args)
            else:
                # Standard upload for small files
                with open(file_path, "rb") as f:
                    self.s3_client.put_object(
                        Bucket=self.bucket,
                        Key=s3_key,
                        Body=f,
                        **extra_args,
                    )

            s3_uri = f"s3://{self.bucket}/{s3_key}"

            logger.info(
                "upload_completed",
                file=str(file_path),
                s3_uri=s3_uri,
                file_size=file_size,
            )

            return s3_uri

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "upload_failed",
                file=str(file_path),
                s3_key=s3_key,
                error_code=error_code,
                error=str(e),
                exc_info=True,
            )
            raise

        except Exception as e:
            logger.error(
                "upload_error",
                file=str(file_path),
                s3_key=s3_key,
                error=str(e),
                exc_info=True,
            )
            raise

    def _upload_with_multipart(
        self,
        file_path: Path,
        s3_key: str,
        extra_args: Dict,
    ) -> None:
        """Upload large file using multipart upload.
        
        Args:
            file_path: Path to file
            s3_key: S3 object key
            extra_args: Additional S3 parameters
        """
        # boto3's upload_file automatically handles multipart uploads
        self.s3_client.upload_file(
            str(file_path),
            self.bucket,
            s3_key,
            ExtraArgs=extra_args,
        )

    def _prepare_metadata(self, file_path: Path, metadata: Dict) -> Dict[str, str]:
        """Prepare S3 metadata from file and additional metadata.
        
        Args:
            file_path: Path to file
            metadata: Additional metadata
            
        Returns:
            Dictionary of S3 metadata (values must be strings)
        """
        s3_metadata = {
            "original-filename": file_path.name,
            "upload-timestamp": datetime.now(timezone.utc).isoformat(),
            "upload-service": "image-upload-microservice",
            "upload-version": "1.0.0",
            "file-size": str(file_path.stat().st_size),
        }

        # Add file hash if available
        if "file_hash" in metadata and isinstance(metadata["file_hash"], dict):
            hash_value = metadata["file_hash"].get("value", "")
            hash_algo = metadata["file_hash"].get("algorithm", "sha256")
            if hash_value:
                s3_metadata["file-hash"] = hash_value
                s3_metadata["hash-algorithm"] = hash_algo

        # Add dimensions if available
        if "image_dimensions" in metadata:
            dims = metadata["image_dimensions"]
            s3_metadata["image-width"] = str(dims.get("width", ""))
            s3_metadata["image-height"] = str(dims.get("height", ""))

        # Add image format if available
        if "image_format" in metadata:
            s3_metadata["image-format"] = str(metadata["image_format"])

        return s3_metadata

    def object_exists_by_hash(self, file_hash: str) -> Optional[str]:
        """Check if an object with the given hash already exists in S3.
        
        Args:
            file_hash: SHA256 hash of the file
            
        Returns:
            S3 URI if object exists, None otherwise
        """
        try:
            # List objects with the hash in metadata
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket, Prefix=self.prefix)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                    
                for obj in page['Contents']:
                    # Get object metadata to check hash
                    try:
                        response = self.s3_client.head_object(
                            Bucket=self.bucket,
                            Key=obj['Key']
                        )
                        metadata = response.get('Metadata', {})
                        object_hash = metadata.get('file-hash', '')
                        
                        if object_hash == file_hash:
                            s3_uri = f"s3://{self.bucket}/{obj['Key']}"
                            logger.info(
                                "object_found_by_hash",
                                hash=file_hash,
                                s3_uri=s3_uri,
                            )
                            return s3_uri
                    except ClientError:
                        # Skip objects we can't access
                        continue
                        
            return None
            
        except ClientError as e:
            logger.warning(
                "hash_check_failed",
                hash=file_hash,
                error=str(e),
            )
            return None

    def verify_bucket_access(self) -> bool:
        """Verify that the S3 bucket is accessible.
        
        Returns:
            True if bucket is accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            logger.info("s3_bucket_verified", bucket=self.bucket)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "s3_bucket_verification_failed",
                bucket=self.bucket,
                error_code=error_code,
                error=str(e),
            )
            return False
