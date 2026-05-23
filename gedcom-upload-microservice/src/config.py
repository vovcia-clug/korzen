"""Configuration management for GEDCOM Upload microservice."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for GEDCOM Upload microservice."""
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # SQS Configuration
    GEDCOM_READY_QUEUE_URL: str = os.getenv("GEDCOM_READY_QUEUE_URL", "")
    SQS_MAX_MESSAGES: int = int(os.getenv("SQS_MAX_MESSAGES", "1"))
    SQS_WAIT_TIME_SECONDS: int = int(os.getenv("SQS_WAIT_TIME_SECONDS", "20"))
    SQS_VISIBILITY_TIMEOUT: int = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "300"))
    
    # S3 Configuration
    S3_OUTPUT_BUCKET: str = os.getenv("S3_OUTPUT_BUCKET", "")
    S3_OUTPUT_PREFIX: str = os.getenv("S3_OUTPUT_PREFIX", "gedcom-files/")
    
    # Application Upload Configuration
    APP_UPLOAD_ENABLED: bool = os.getenv("APP_UPLOAD_ENABLED", "true").lower() == "true"
    APP_URL: Optional[str] = os.getenv("APP_URL")
    APP_API_KEY: Optional[str] = os.getenv("APP_API_KEY")
    APP_UPLOAD_TIMEOUT: int = int(os.getenv("APP_UPLOAD_TIMEOUT", "30"))
    APP_PARSE_TIMEOUT: int = int(os.getenv("APP_PARSE_TIMEOUT", "300"))
    APP_AUTO_PARSE: bool = os.getenv("APP_AUTO_PARSE", "true").lower() == "true"
    
    # Retry Configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY_SECONDS: int = int(os.getenv("RETRY_DELAY_SECONDS", "5"))
    
    # Processing Configuration
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/gedcom-upload")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Graceful Shutdown
    SHUTDOWN_GRACE_PERIOD: int = int(os.getenv("SHUTDOWN_GRACE_PERIOD", "30"))
    
    @classmethod
    def get_aws_config(cls) -> dict:
        """
        Get AWS configuration dictionary for boto3.
        
        Returns:
            Dictionary with AWS credentials and region
        """
        config = {
            "region_name": cls.AWS_REGION
        }
        
        # Add credentials if provided
        if cls.AWS_ACCESS_KEY_ID and cls.AWS_SECRET_ACCESS_KEY:
            config["aws_access_key_id"] = cls.AWS_ACCESS_KEY_ID
            config["aws_secret_access_key"] = cls.AWS_SECRET_ACCESS_KEY
        
        return config
    
    @classmethod
    def validate(cls) -> None:
        """
        Validate required configuration values.
        
        Raises:
            ValueError: If required configuration is missing
        """
        errors = []
        
        if not cls.GEDCOM_READY_QUEUE_URL:
            errors.append("GEDCOM_READY_QUEUE_URL is required")
        
        if not cls.S3_OUTPUT_BUCKET:
            errors.append("S3_OUTPUT_BUCKET is required")
        
        if cls.APP_UPLOAD_ENABLED and not cls.APP_URL:
            errors.append("APP_URL is required when APP_UPLOAD_ENABLED is true")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
    
    @classmethod
    def log_config(cls, logger) -> None:
        """
        Log configuration values (excluding sensitive data).
        
        Args:
            logger: Logger instance
        """
        logger.info("=== GEDCOM Upload Microservice Configuration ===")
        logger.info(f"AWS Region: {cls.AWS_REGION}")
        logger.info(f"GEDCOM Ready Queue: {cls.GEDCOM_READY_QUEUE_URL}")
        logger.info(f"S3 Output Bucket: {cls.S3_OUTPUT_BUCKET}")
        logger.info(f"S3 Output Prefix: {cls.S3_OUTPUT_PREFIX}")
        logger.info(f"Application Upload Enabled: {cls.APP_UPLOAD_ENABLED}")
        if cls.APP_UPLOAD_ENABLED:
            logger.info(f"Application URL: {cls.APP_URL}")
            logger.info(f"Auto Parse: {cls.APP_AUTO_PARSE}")
        logger.info(f"Max Retries: {cls.MAX_RETRIES}")
        logger.info(f"Log Level: {cls.LOG_LEVEL}")
        logger.info("=" * 50)
