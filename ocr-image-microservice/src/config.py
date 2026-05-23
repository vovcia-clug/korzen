"""Configuration management for OCR Image microservice."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for OCR Image microservice."""
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    
    # SQS Configuration
    IMAGE_UPLOAD_QUEUE_URL: str = os.getenv("IMAGE_UPLOAD_QUEUE_URL", "")
    OCR_RESULTS_QUEUE_URL: str = os.getenv("OCR_RESULTS_QUEUE_URL", "")
    SQS_MAX_MESSAGES: int = int(os.getenv("SQS_MAX_MESSAGES", "1"))
    SQS_WAIT_TIME_SECONDS: int = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))
    SQS_VISIBILITY_TIMEOUT: int = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "300"))
    
    # S3 Configuration
    S3_INPUT_BUCKET: str = os.getenv("S3_INPUT_BUCKET", "")
    S3_OUTPUT_BUCKET: str = os.getenv("S3_OUTPUT_BUCKET", "")
    S3_OUTPUT_PREFIX: str = os.getenv("S3_OUTPUT_PREFIX", "ocr-results/")
    
    # OCR Configuration
    DATALAB_API_KEY: str = os.getenv("DATALAB_API_KEY", "")
    OCR_OUTPUT_FORMAT: str = os.getenv("OCR_OUTPUT_FORMAT", "markdown")
    OCR_MODE: str = os.getenv("OCR_MODE", "accurate")
    OCR_PAGINATE: bool = os.getenv("OCR_PAGINATE", "true").lower() == "true"
    
    # Processing Configuration
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/ocr-processing")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Service Configuration
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "5"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate required configuration values.
        
        Raises:
            ValueError: If required configuration is missing
        """
        required_fields = [
            ("AWS_ACCESS_KEY_ID", cls.AWS_ACCESS_KEY_ID),
            ("AWS_SECRET_ACCESS_KEY", cls.AWS_SECRET_ACCESS_KEY),
            ("AWS_REGION", cls.AWS_REGION),
            ("IMAGE_UPLOAD_QUEUE_URL", cls.IMAGE_UPLOAD_QUEUE_URL),
            ("OCR_RESULTS_QUEUE_URL", cls.OCR_RESULTS_QUEUE_URL),
            ("S3_INPUT_BUCKET", cls.S3_INPUT_BUCKET),
            ("S3_OUTPUT_BUCKET", cls.S3_OUTPUT_BUCKET),
            ("DATALAB_API_KEY", cls.DATALAB_API_KEY),
        ]
        
        missing_fields = [
            field_name for field_name, field_value in required_fields
            if not field_value
        ]
        
        if missing_fields:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing_fields)}"
            )
    
    @classmethod
    def get_aws_config(cls) -> dict:
        """
        Get AWS configuration dictionary for boto3.
        
        Returns:
            Dictionary with AWS credentials and region
        """
        return {
            "aws_access_key_id": cls.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": cls.AWS_SECRET_ACCESS_KEY,
            "region_name": cls.AWS_REGION,
        }
    
    @classmethod
    def display_config(cls) -> str:
        """
        Display configuration (with sensitive values masked).
        
        Returns:
            String representation of configuration
        """
        def mask_value(value: str, show_chars: int = 4) -> str:
            """Mask sensitive values, showing only last few characters."""
            if not value or len(value) <= show_chars:
                return "***"
            return f"***{value[-show_chars:]}"
        
        config_str = f"""
OCR Image Microservice Configuration:
=====================================
AWS Region: {cls.AWS_REGION}
AWS Access Key: {mask_value(cls.AWS_ACCESS_KEY_ID)}
AWS Secret Key: {mask_value(cls.AWS_SECRET_ACCESS_KEY)}

SQS Queues:
  Input Queue: {cls.IMAGE_UPLOAD_QUEUE_URL}
  Output Queue: {cls.OCR_RESULTS_QUEUE_URL}
  Max Messages: {cls.SQS_MAX_MESSAGES}
  Wait Time: {cls.SQS_WAIT_TIME_SECONDS}s
  Visibility Timeout: {cls.SQS_VISIBILITY_TIMEOUT}s

S3 Buckets:
  Input Bucket: {cls.S3_INPUT_BUCKET}
  Output Bucket: {cls.S3_OUTPUT_BUCKET}
  Output Prefix: {cls.S3_OUTPUT_PREFIX}

OCR Settings:
  Datalab API Key: {mask_value(cls.DATALAB_API_KEY)}
  Output Format: {cls.OCR_OUTPUT_FORMAT}
  Mode: {cls.OCR_MODE}
  Paginate: {cls.OCR_PAGINATE}

Processing:
  Temp Directory: {cls.TEMP_DIR}
  Poll Interval: {cls.POLL_INTERVAL_SECONDS}s
  Max Retries: {cls.MAX_RETRIES}
  Log Level: {cls.LOG_LEVEL}
"""
        return config_str
