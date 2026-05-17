"""Configuration management for OCR microservice."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # SQS Configuration
    SQS_QUEUE_URL: Optional[str] = os.getenv("SQS_QUEUE_URL")
    SQS_MAX_MESSAGES: int = int(os.getenv("SQS_MAX_MESSAGES", "1"))
    SQS_WAIT_TIME_SECONDS: int = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))
    SQS_VISIBILITY_TIMEOUT: int = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "300"))
    
    # S3 Configuration
    S3_INPUT_BUCKET: Optional[str] = os.getenv("S3_INPUT_BUCKET")
    S3_OUTPUT_BUCKET: Optional[str] = os.getenv("S3_OUTPUT_BUCKET")
    S3_OUTPUT_PREFIX: str = os.getenv("S3_OUTPUT_PREFIX", "ocr-results/")
    S3_STRUCTURED_PREFIX: str = os.getenv("S3_STRUCTURED_PREFIX", "structured-data/")
    S3_GEDCOM_PREFIX: str = os.getenv("S3_GEDCOM_PREFIX", "gedcom-files/")
    
    # Application Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/ocr-processing")
    
    # Retry Configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_BASE: float = float(os.getenv("RETRY_BACKOFF_BASE", "2.0"))
    RETRY_BACKOFF_MAX: float = float(os.getenv("RETRY_BACKOFF_MAX", "60.0"))
    
    # OCR Configuration
    OCR_OUTPUT_FORMAT: str = os.getenv("OCR_OUTPUT_FORMAT", "markdown")
    OCR_MODE: str = os.getenv("OCR_MODE", "accurate")
    OCR_PAGINATE: bool = os.getenv("OCR_PAGINATE", "true").lower() == "true"
    
    # OpenRouter Configuration
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_TIMEOUT: int = int(os.getenv("OPENROUTER_TIMEOUT", "120"))
    
    # Processing Options
    ENABLE_OPENROUTER: bool = os.getenv("ENABLE_OPENROUTER", "true").lower() == "true"
    ENABLE_GEDCOM_GENERATION: bool = os.getenv("ENABLE_GEDCOM_GENERATION", "true").lower() == "true"
    SAVE_INTERMEDIATE_RESULTS: bool = os.getenv("SAVE_INTERMEDIATE_RESULTS", "true").lower() == "true"
    
    # Hosted Application Integration
    HOSTED_APP_URL: str = os.getenv("HOSTED_APP_URL", "")
    HOSTED_APP_API_KEY: str = os.getenv("HOSTED_APP_API_KEY", "")
    ENABLE_AUTO_UPLOAD: bool = os.getenv("ENABLE_AUTO_UPLOAD", "true").lower() == "true"
    
    @classmethod
    def validate(cls) -> None:
        """Validate that all required configuration is present."""
        required_fields = [
            ("AWS_ACCESS_KEY_ID", cls.AWS_ACCESS_KEY_ID),
            ("AWS_SECRET_ACCESS_KEY", cls.AWS_SECRET_ACCESS_KEY),
            ("SQS_QUEUE_URL", cls.SQS_QUEUE_URL),
            ("S3_INPUT_BUCKET", cls.S3_INPUT_BUCKET),
            ("S3_OUTPUT_BUCKET", cls.S3_OUTPUT_BUCKET),
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
        """Get AWS configuration dictionary for boto3 clients."""
        return {
            "region_name": cls.AWS_REGION,
            "aws_access_key_id": cls.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": cls.AWS_SECRET_ACCESS_KEY,
        }
    
    @classmethod
    def display_config(cls) -> str:
        """Return a safe string representation of configuration (without secrets)."""
        return f"""
Configuration:
  AWS Region: {cls.AWS_REGION}
  SQS Queue URL: {cls.SQS_QUEUE_URL}
  S3 Input Bucket: {cls.S3_INPUT_BUCKET}
  S3 Output Bucket: {cls.S3_OUTPUT_BUCKET}
  S3 Output Prefix: {cls.S3_OUTPUT_PREFIX}
  Log Level: {cls.LOG_LEVEL}
  Max Retries: {cls.MAX_RETRIES}
  OCR Mode: {cls.OCR_MODE}
  OCR Output Format: {cls.OCR_OUTPUT_FORMAT}
"""
