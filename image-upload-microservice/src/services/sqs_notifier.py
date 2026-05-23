"""SQS notification service.

This module handles sending notification messages to AWS SQS queue
when images are successfully uploaded to S3.
"""

import hashlib
import json
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


class SQSNotifier:
    """Handles sending notification messages to SQS."""

    def __init__(
        self,
        queue_url: str,
        region: str = "us-east-1",
        batch_size: int = 10,
        max_retries: int = 3,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """Initialize the SQS notifier.
        
        Args:
            queue_url: SQS queue URL
            region: AWS region
            batch_size: Maximum messages per batch (1-10)
            max_retries: Maximum retry attempts
            aws_access_key_id: AWS access key (optional if using IAM roles)
            aws_secret_access_key: AWS secret key (optional if using IAM roles)
        """
        self.queue_url = queue_url
        self.batch_size = min(batch_size, 10)  # SQS limit is 10
        self.max_retries = max_retries

        # Detect if this is a FIFO queue
        self.is_fifo_queue = queue_url.endswith(".fifo")

        # Configure boto3 client
        boto_config = BotoConfig(
            region_name=region,
            retries={"max_attempts": max_retries, "mode": "adaptive"},
        )

        # Create SQS client
        session_kwargs = {}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key

        session = boto3.Session(**session_kwargs)
        self.sqs_client = session.client("sqs", config=boto_config)

        logger.info(
            "sqs_notifier_initialized",
            queue_url=queue_url,
            region=region,
            batch_size=self.batch_size,
            is_fifo_queue=self.is_fifo_queue,
        )
        
        # DEBUG: Log diagnostic information
        logger.debug(
            "sqs_queue_type_detection",
            queue_url=queue_url,
            is_fifo=self.is_fifo_queue,
            requires_message_group_id=self.is_fifo_queue,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        retry=retry_if_exception_type((ClientError, ConnectionError)),
        reraise=True,
    )
    def send_notification(
        self,
        s3_uri: str,
        original_filename: str,
        metadata: Dict,
    ) -> str:
        """Send notification message to SQS.
        
        Args:
            s3_uri: S3 URI of uploaded image
            original_filename: Original filename
            metadata: Image metadata dictionary
            
        Returns:
            SQS message ID
            
        Raises:
            ClientError: If message send fails after retries
        """
        # Construct message body
        message_body = self._construct_message_body(
            s3_uri=s3_uri,
            original_filename=original_filename,
            metadata=metadata,
        )

        # Construct message attributes
        message_attributes = self._construct_message_attributes(metadata)

        logger.info(
            "notification_sending",
            s3_uri=s3_uri,
            filename=original_filename,
            is_fifo_queue=self.is_fifo_queue,
        )

        # Prepare base send_message parameters
        send_params = {
            "QueueUrl": self.queue_url,
            "MessageBody": json.dumps(message_body),
            "MessageAttributes": message_attributes,
        }

        # Add FIFO-specific parameters if needed
        if self.is_fifo_queue:
            # MessageGroupId: Group related messages together
            # Using a constant value means all messages are in the same group
            message_group_id = "image-uploads"
            
            # MessageDeduplicationId: Prevent duplicate messages
            # Use file hash if available, otherwise generate from S3 URI
            file_hash = metadata.get("file_hash", {}).get("value", "")
            if file_hash:
                message_deduplication_id = file_hash
            else:
                # Fallback: hash the S3 URI + timestamp
                dedup_content = f"{s3_uri}:{original_filename}"
                message_deduplication_id = hashlib.sha256(
                    dedup_content.encode()
                ).hexdigest()
            
            send_params["MessageGroupId"] = message_group_id
            send_params["MessageDeduplicationId"] = message_deduplication_id
            
            logger.debug(
                "fifo_parameters_added",
                message_group_id=message_group_id,
                message_deduplication_id=message_deduplication_id[:16] + "...",
                s3_uri=s3_uri,
            )

        try:
            response = self.sqs_client.send_message(**send_params)

            message_id = response.get("MessageId", "")

            logger.info(
                "notification_sent",
                message_id=message_id,
                s3_uri=s3_uri,
                filename=original_filename,
            )

            return message_id

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "notification_failed",
                s3_uri=s3_uri,
                error_code=error_code,
                error=str(e),
                exc_info=True,
            )
            raise

        except Exception as e:
            logger.error(
                "notification_error",
                s3_uri=s3_uri,
                error=str(e),
                exc_info=True,
            )
            raise

    def _construct_message_body(
        self,
        s3_uri: str,
        original_filename: str,
        metadata: Dict,
    ) -> Dict:
        """Construct SQS message body.
        
        Args:
            s3_uri: S3 URI of uploaded image
            original_filename: Original filename
            metadata: Image metadata
            
        Returns:
            Message body dictionary
        """
        message = {
            "s3_uri": s3_uri,
            "metadata": {
                "original_filename": original_filename,
                "upload_timestamp": datetime.now(timezone.utc).isoformat(),
                "file_size_bytes": metadata.get("file_size_bytes", 0),
                "content_type": metadata.get("content_type", "application/octet-stream"),
            },
            "source_service": "image-upload-microservice",
            "message_version": "1.0",
        }

        # Add image dimensions if available
        if "image_dimensions" in metadata:
            message["metadata"]["image_dimensions"] = metadata["image_dimensions"]

        # Add file hash if available
        if "file_hash" in metadata:
            message["metadata"]["file_hash"] = metadata["file_hash"]

        # Add image format if available
        if "image_format" in metadata:
            message["metadata"]["image_format"] = metadata["image_format"]
        
        # Add Skanoteka metadata if available
        if "skanoteka" in metadata and isinstance(metadata["skanoteka"], dict):
            message["metadata"]["skanoteka"] = metadata["skanoteka"]

        return message

    def _construct_message_attributes(self, metadata: Dict) -> Dict:
        """Construct SQS message attributes.
        
        Args:
            metadata: Image metadata
            
        Returns:
            Message attributes dictionary
        """
        attributes = {
            "ContentType": {
                "StringValue": "application/json",
                "DataType": "String",
            },
            "SourceService": {
                "StringValue": "image-upload-microservice",
                "DataType": "String",
            },
            "EventType": {
                "StringValue": "image.uploaded",
                "DataType": "String",
            },
            "Timestamp": {
                "StringValue": datetime.now(timezone.utc).isoformat(),
                "DataType": "String",
            },
        }

        # Add image format if available
        if "image_format" in metadata:
            attributes["ImageFormat"] = {
                "StringValue": str(metadata["image_format"]),
                "DataType": "String",
            }

        # Add file size if available
        if "file_size_bytes" in metadata:
            attributes["FileSize"] = {
                "StringValue": str(metadata["file_size_bytes"]),
                "DataType": "Number",
            }

        return attributes

    def verify_queue_access(self) -> bool:
        """Verify that the SQS queue is accessible.
        
        Returns:
            True if queue is accessible, False otherwise
        """
        try:
            self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_url,
                AttributeNames=["QueueArn"],
            )
            logger.info("sqs_queue_verified", queue_url=self.queue_url)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                "sqs_queue_verification_failed",
                queue_url=self.queue_url,
                error_code=error_code,
                error=str(e),
            )
            return False
