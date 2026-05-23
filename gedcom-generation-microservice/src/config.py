"""Configuration for GEDCOM generation microservice."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for GEDCOM generation service."""
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    
    # SQS Configuration
    OCR_RESULTS_QUEUE_URL: str = os.getenv("OCR_RESULTS_QUEUE_URL", "")
    GEDCOM_READY_QUEUE_URL: str = os.getenv("GEDCOM_READY_QUEUE_URL", "")
    SQS_MAX_MESSAGES: int = int(os.getenv("SQS_MAX_MESSAGES", "1"))
    SQS_WAIT_TIME_SECONDS: int = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))
    SQS_VISIBILITY_TIMEOUT: int = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "300"))
    
    # S3 Configuration
    S3_OUTPUT_BUCKET: str = os.getenv("S3_OUTPUT_BUCKET", "")
    S3_GEDCOM_PREFIX: str = os.getenv("S3_GEDCOM_PREFIX", "gedcom-files/")
    
    # OpenRouter Configuration
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1"
    )
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL",
        "google/gemini-flash-1.5"
    )
    OPENROUTER_TIMEOUT: int = int(os.getenv("OPENROUTER_TIMEOUT", "300"))
    
    # Document Grouping Configuration
    GROUPING_TIMEOUT_SECONDS: int = int(os.getenv("GROUPING_TIMEOUT_SECONDS", "300"))
    GROUPING_CHECK_INTERVAL: int = int(os.getenv("GROUPING_CHECK_INTERVAL", "30"))
    MAX_PAGES_PER_GROUP: int = int(os.getenv("MAX_PAGES_PER_GROUP", "1000"))
    
    # Redis Configuration (optional, for distributed grouping)
    USE_REDIS: bool = os.getenv("USE_REDIS", "false").lower() == "true"
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_KEY_PREFIX: str = os.getenv("REDIS_KEY_PREFIX", "gedcom:docgroup:")
    
    # GEDCOM Configuration
    GEDCOM_VERSION: str = os.getenv("GEDCOM_VERSION", "5.5.1")
    ENABLE_GEDCOM_VALIDATION: bool = os.getenv(
        "ENABLE_GEDCOM_VALIDATION",
        "true"
    ).lower() == "true"
    STRICT_VALIDATION: bool = os.getenv("STRICT_VALIDATION", "false").lower() == "true"
    
    # Retry Configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF_BASE: int = int(os.getenv("RETRY_BACKOFF_BASE", "2"))
    RETRY_BACKOFF_MAX: int = int(os.getenv("RETRY_BACKOFF_MAX", "60"))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Langfuse Configuration (optional, for LLM observability)
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
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
            ("OCR_RESULTS_QUEUE_URL", cls.OCR_RESULTS_QUEUE_URL),
            ("GEDCOM_READY_QUEUE_URL", cls.GEDCOM_READY_QUEUE_URL),
            ("S3_OUTPUT_BUCKET", cls.S3_OUTPUT_BUCKET),
            ("OPENROUTER_API_KEY", cls.OPENROUTER_API_KEY),
        ]
        
        missing = []
        for field_name, field_value in required_fields:
            if not field_value:
                missing.append(field_name)
        
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}"
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
            "region_name": cls.AWS_REGION
        }
    
    @classmethod
    def to_dict(cls) -> dict:
        """
        Convert configuration to dictionary (for logging, excluding secrets).
        
        Returns:
            Dictionary with non-sensitive configuration
        """
        return {
            "aws_region": cls.AWS_REGION,
            "ocr_results_queue_url": cls.OCR_RESULTS_QUEUE_URL,
            "gedcom_ready_queue_url": cls.GEDCOM_READY_QUEUE_URL,
            "s3_output_bucket": cls.S3_OUTPUT_BUCKET,
            "s3_gedcom_prefix": cls.S3_GEDCOM_PREFIX,
            "openrouter_model": cls.OPENROUTER_MODEL,
            "grouping_timeout_seconds": cls.GROUPING_TIMEOUT_SECONDS,
            "use_redis": cls.USE_REDIS,
            "redis_host": cls.REDIS_HOST if cls.USE_REDIS else "N/A",
            "gedcom_version": cls.GEDCOM_VERSION,
            "enable_validation": cls.ENABLE_GEDCOM_VALIDATION,
            "log_level": cls.LOG_LEVEL,
            "langfuse_configured": cls.is_langfuse_configured(),
            "langfuse_host": cls.LANGFUSE_HOST if cls.is_langfuse_configured() else "N/A"
        }
    
    @classmethod
    def is_langfuse_configured(cls) -> bool:
        """
        Check if Langfuse is properly configured.
        
        Returns:
            True if Langfuse has required credentials
        """
        return (
            bool(cls.LANGFUSE_PUBLIC_KEY) and
            bool(cls.LANGFUSE_SECRET_KEY)
        )
