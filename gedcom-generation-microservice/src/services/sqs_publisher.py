"""SQS publisher for sending GEDCOM ready messages."""
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SQSPublisher:
    """Publisher for AWS SQS messages."""
    
    def __init__(
        self,
        aws_config: dict,
        queue_url: str
    ):
        """
        Initialize SQS publisher.
        
        Args:
            aws_config: AWS configuration dictionary for boto3
            queue_url: SQS queue URL for publishing messages
        """
        self.queue_url = queue_url
        
        # Create SQS client
        self.sqs_client = boto3.client("sqs", **aws_config)
        
        logger.info(f"SQSPublisher initialized - Queue: {queue_url}")
    
    def publish_gedcom_ready(
        self,
        document_metadata: Dict[str, Any],
        gedcom_data: Dict[str, Any],
        source_ocr_uris: list = None,
        processing_metadata: Dict[str, Any] = None
    ) -> str:
        """
        Publish GEDCOM ready message to SQS queue.
        
        Args:
            document_metadata: Document metadata (document_id, title, etc.)
            gedcom_data: GEDCOM data (content, filename, s3_uri, validation_status, counts)
            source_ocr_uris: List of source OCR S3 URIs (optional)
            processing_metadata: Processing metadata (optional)
        
        Returns:
            Message ID of published message
        
        Raises:
            ClientError: If SQS publish operation fails
        """
        # Build message
        message = {
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "document_metadata": document_metadata,
            "gedcom_data": gedcom_data
        }
        
        if source_ocr_uris:
            message["source_ocr_uris"] = source_ocr_uris
        
        if processing_metadata:
            message["metadata"] = processing_metadata
        
        try:
            logger.info(
                f"Publishing GEDCOM ready message for document: "
                f"{document_metadata.get('document_id')}"
            )
            
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message)
            )
            
            message_id = response.get("MessageId")
            logger.info(f"Successfully published message: {message_id}")
            
            return message_id
            
        except ClientError as e:
            logger.error(f"Failed to publish message to SQS: {e}")
            raise
    
    def publish_message(
        self,
        message_body: Dict[str, Any]
    ) -> str:
        """
        Publish arbitrary message to SQS queue.
        
        Args:
            message_body: Message body as dictionary
        
        Returns:
            Message ID of published message
        
        Raises:
            ClientError: If SQS publish operation fails
        """
        try:
            logger.debug(f"Publishing message to SQS")
            
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body)
            )
            
            message_id = response.get("MessageId")
            logger.debug(f"Successfully published message: {message_id}")
            
            return message_id
            
        except ClientError as e:
            logger.error(f"Failed to publish message to SQS: {e}")
            raise
