"""Configuration management for the image upload microservice.

This module handles environment variable loading, validation, and
provides a strongly-typed configuration object for the application.
"""

import os
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Config(BaseModel):
    """Application configuration loaded from environment variables."""

    # === Directory Watching ===
    watch_directory: Path = Field(
        description="Directory to monitor for new image files"
    )
    watch_recursive: bool = Field(
        default=False,
        description="Enable recursive subdirectory monitoring"
    )
    debounce_seconds: float = Field(
        default=2.0,
        ge=0.1,
        le=30.0,
        description="Seconds to wait before processing file (avoid partial writes)"
    )

    # === AWS Configuration ===
    aws_region: str = Field(
        description="AWS region for S3 and SQS"
    )
    aws_access_key_id: str | None = Field(
        default=None,
        description="AWS access key (optional if using IAM roles)"
    )
    aws_secret_access_key: str | None = Field(
        default=None,
        description="AWS secret key (optional if using IAM roles)"
    )

    # === S3 Configuration ===
    s3_bucket: str = Field(
        description="Target S3 bucket name"
    )
    s3_prefix: str = Field(
        default="uploads/",
        description="Object key prefix"
    )
    s3_server_side_encryption: str = Field(
        default="AES256",
        description="Server-side encryption algorithm"
    )
    s3_storage_class: str = Field(
        default="STANDARD",
        description="S3 storage class"
    )
    multipart_threshold_mb: int = Field(
        default=5,
        ge=5,
        le=100,
        description="File size threshold for multipart uploads (MB)"
    )

    # === SQS Configuration ===
    sqs_queue_url: str = Field(
        description="Target SQS queue URL"
    )
    sqs_batch_size: int = Field(
        default=10,
        ge=1,
        le=10,
        description="Messages per batch"
    )

    # === Image Detection ===
    supported_extensions: List[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"],
        description="Allowed image file extensions"
    )
    min_image_size_bytes: int = Field(
        default=1024,
        ge=0,
        description="Minimum file size"
    )
    max_image_size_bytes: int = Field(
        default=104857600,  # 100MB
        ge=1024,
        description="Maximum file size"
    )
    strict_validation: bool = Field(
        default=True,
        description="Enable image header validation"
    )

    # === Post-Upload Actions ===
    post_upload_action: Literal["keep", "archive", "delete"] = Field(
        default="keep",
        description="Action after successful upload"
    )
    archive_directory: Path | None = Field(
        default=None,
        description="Directory for archived files (required if action=archive)"
    )

    # === Application Configuration ===
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    max_concurrent_uploads: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum parallel uploads"
    )
    upload_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Maximum time for complete workflow"
    )

    # === Retry Configuration ===
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts"
    )
    retry_backoff_base: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Base for exponential backoff"
    )
    retry_backoff_max: float = Field(
        default=60.0,
        ge=1.0,
        le=300.0,
        description="Maximum backoff delay"
    )

    model_config = {"arbitrary_types_allowed": True}

    @field_validator("watch_directory", mode="before")
    @classmethod
    def validate_watch_directory(cls, v: str | Path) -> Path:
        """Validate that the watch directory exists."""
        path = Path(v) if isinstance(v, str) else v
        if not path.exists():
            raise ValueError(f"Watch directory does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Watch directory is not a directory: {path}")
        return path

    @field_validator("archive_directory", mode="before")
    @classmethod
    def validate_archive_directory(cls, v: str | Path | None) -> Path | None:
        """Validate archive directory if provided."""
        if v is None:
            return None
        path = Path(v) if isinstance(v, str) else v
        # Create archive directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("supported_extensions", mode="before")
    @classmethod
    def normalize_extensions(cls, v: str | List[str]) -> List[str]:
        """Normalize file extensions to lowercase with leading dots."""
        if isinstance(v, str):
            extensions = [ext.strip() for ext in v.split(",")]
        else:
            extensions = v

        normalized = []
        for ext in extensions:
            ext = ext.lower().strip()
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized.append(ext)
        return normalized

    @model_validator(mode="after")
    def validate_archive_action(self) -> "Config":
        """Validate that archive_directory is set if action is archive."""
        if self.post_upload_action == "archive" and self.archive_directory is None:
            raise ValueError(
                "archive_directory must be set when post_upload_action is 'archive'"
            )
        return self

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.
        
        Returns:
            Config instance populated from environment
            
        Raises:
            ValidationError: If required variables are missing or invalid
        """
        return cls(
            # Directory Watching
            watch_directory=os.getenv("WATCH_DIRECTORY", "/app/watched-images"),
            watch_recursive=os.getenv("WATCH_RECURSIVE", "false").lower() == "true",
            debounce_seconds=float(os.getenv("DEBOUNCE_SECONDS", "2.0")),
            
            # AWS Configuration
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            
            # S3 Configuration
            s3_bucket=os.getenv("AWS_S3_BUCKET", os.getenv("S3_BUCKET", "")),
            s3_prefix=os.getenv("S3_PREFIX", "uploads/"),
            s3_server_side_encryption=os.getenv("S3_SERVER_SIDE_ENCRYPTION", "AES256"),
            s3_storage_class=os.getenv("S3_STORAGE_CLASS", "STANDARD"),
            multipart_threshold_mb=int(os.getenv("MULTIPART_THRESHOLD_MB", "5")),
            
            # SQS Configuration
            sqs_queue_url=os.getenv("AWS_SQS_QUEUE_URL", os.getenv("SQS_QUEUE_URL", "")),
            sqs_batch_size=int(os.getenv("SQS_BATCH_SIZE", "10")),
            
            # Image Detection
            supported_extensions=os.getenv(
                "SUPPORTED_EXTENSIONS",
                "jpg,jpeg,png,gif,bmp,tiff,tif,webp"
            ),
            min_image_size_bytes=int(os.getenv("MIN_IMAGE_SIZE_BYTES", "1024")),
            max_image_size_bytes=int(os.getenv("MAX_IMAGE_SIZE_BYTES", "104857600")),
            strict_validation=os.getenv("STRICT_VALIDATION", "true").lower() == "true",
            
            # Post-Upload Actions
            post_upload_action=os.getenv("POST_UPLOAD_ACTION", "keep"),
            archive_directory=os.getenv("ARCHIVE_DIRECTORY"),
            
            # Application Configuration
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            max_concurrent_uploads=int(os.getenv("MAX_CONCURRENT_UPLOADS", "3")),
            upload_timeout_seconds=int(os.getenv("UPLOAD_TIMEOUT_SECONDS", "300")),
            
            # Retry Configuration
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            retry_backoff_base=float(os.getenv("RETRY_BACKOFF_BASE", "2.0")),
            retry_backoff_max=float(os.getenv("RETRY_BACKOFF_MAX", "60.0")),
        )
