"""S3 handler for uploading GEDCOM files."""
import os
from pathlib import Path
from typing import Optional
import boto3
from botocore.exceptions import ClientError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class S3Handler:
    """Handle S3 upload operations for GEDCOM files."""
    
    def __init__(
        self,
        aws_config: dict,
        output_bucket: str,
        output_prefix: str = "gedcom-files/"
    ):
        """
        Initialize S3 handler.
        
        Args:
            aws_config: AWS configuration dictionary for boto3
            output_bucket: S3 bucket name for output GEDCOM files
            output_prefix: Prefix for output files in S3
        """
        self.output_bucket = output_bucket
        self.output_prefix = output_prefix
        
        # Create S3 client
        self.s3_client = boto3.client("s3", **aws_config)
        
        logger.info(
            f"S3Handler initialized - Output: {output_bucket}/{output_prefix}"
        )
    
    def upload_gedcom(
        self,
        content: str,
        document_id: str,
        filename: Optional[str] = None
    ) -> str:
        """
        Upload GEDCOM content to S3.
        
        Args:
            content: GEDCOM file content as string
            document_id: Document identifier for organizing files
            filename: Optional custom filename (defaults to document_id.ged)
        
        Returns:
            S3 URI of uploaded GEDCOM file
        
        Raises:
            ClientError: If S3 upload fails
        """
        # Generate output S3 key
        if filename is None:
            filename = f"{document_id}.ged"
        
        output_key = f"{self.output_prefix}{filename}"
        
        try:
            logger.info(
                f"Uploading GEDCOM ({len(content)} bytes) to "
                f"s3://{self.output_bucket}/{output_key}"
            )
            
            # Upload string content directly
            self.s3_client.put_object(
                Bucket=self.output_bucket,
                Key=output_key,
                Body=content.encode('utf-8'),
                ContentType='text/x-gedcom'
            )
            
            s3_uri = f"s3://{self.output_bucket}/{output_key}"
            logger.info(f"Successfully uploaded GEDCOM to {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            logger.error(f"Failed to upload GEDCOM: {e}")
            raise
    
    def upload_content(
        self,
        content: str,
        s3_key: str,
        content_type: str = "text/plain"
    ) -> str:
        """
        Upload arbitrary content to S3.
        
        Args:
            content: Content to upload as string
            s3_key: Full S3 key (including prefix)
            content_type: MIME type of the content
        
        Returns:
            S3 URI of uploaded file
        
        Raises:
            ClientError: If S3 upload fails
        """
        try:
            logger.info(
                f"Uploading content ({len(content)} bytes) to "
                f"s3://{self.output_bucket}/{s3_key}"
            )
            
            self.s3_client.put_object(
                Bucket=self.output_bucket,
                Key=s3_key,
                Body=content.encode('utf-8'),
                ContentType=content_type
            )
            
            s3_uri = f"s3://{self.output_bucket}/{s3_key}"
            logger.info(f"Successfully uploaded content to {s3_uri}")
            return s3_uri
            
        except ClientError as e:
            logger.error(f"Failed to upload content: {e}")
            raise
