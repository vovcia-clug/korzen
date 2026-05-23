"""SQS publisher for sending OCR results to the next service."""
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SQSPublisher:
    """Publisher for sending messages to AWS SQS."""
    
    def __init__(self, aws_config: dict, queue_url: str):
        """
        Initialize SQS publisher.
        
        Args:
            aws_config: AWS configuration dictionary for boto3
            queue_url: SQS queue URL to publish to
        """
        self.queue_url = queue_url
        
        # Create SQS client
        self.sqs_client = boto3.client("sqs", **aws_config)
        
        logger.info(f"SQSPublisher initialized - Queue: {queue_url}")
    
    def publish_ocr_result(
        self,
        source_image_uri: str,
        ocr_result_uri: str,
        markdown_text: str,
        metadata: Dict[str, Any],
        source_image_dimensions: tuple = None
    ) -> str:
        """
        Publish OCR result message to SQS queue.
        
        Message format follows the OCR Results Message specification from
        the architecture document (Section 5.1).
        
        Args:
            source_image_uri: S3 URI of the source image
            ocr_result_uri: S3 URI of the OCR markdown result
            markdown_text: OCR text content
            metadata: Document metadata (document_id, page_number, etc.)
            source_image_dimensions: Optional tuple of (width, height)
        
        Returns:
            Message ID of the published message
        
        Raises:
            ClientError: If SQS publish operation fails
        """
        try:
            # Generate message ID and timestamp
            message_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # Build message payload
            message = {
                "message_id": message_id,
                "timestamp": timestamp,
                "metadata": {
                    "document_id": metadata.get("document_id"),
                    "page_number": metadata.get("page_number"),
                    "total_pages": metadata.get("total_pages"),
                    "document_title": metadata.get("document_title"),
                    "date_range": metadata.get("date_range"),
                    "location": metadata.get("location"),
                    "record_type": metadata.get("record_type"),
                    "language": metadata.get("language"),
                    "source": metadata.get("source")
                },
                "ocr_result": {
                    "markdown_text": markdown_text,
                    "s3_uri": ocr_result_uri,
                    "character_count": len(markdown_text)
                },
                "source_image": {
                    "s3_uri": source_image_uri,
                    "filename": metadata.get("filename")
                }
            }
            
            # Add image dimensions if available
            if source_image_dimensions:
                message["source_image"]["width"] = source_image_dimensions[0]
                message["source_image"]["height"] = source_image_dimensions[1]
            elif "image_width" in metadata and "image_height" in metadata:
                message["source_image"]["width"] = metadata["image_width"]
                message["source_image"]["height"] = metadata["image_height"]
            
            # Remove None values from metadata to keep message clean
            message["metadata"] = {
                k: v for k, v in message["metadata"].items() if v is not None
            }
            
            # Convert to JSON
            message_body = json.dumps(message, ensure_ascii=False)
            
            logger.info(
                f"Publishing OCR result message - "
                f"document_id={metadata.get('document_id')}, "
                f"page_number={metadata.get('page_number')}"
            )
            logger.debug(f"Message body: {message_body[:500]}...")
            
            # Send message to SQS
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body
            )
            
            sqs_message_id = response.get("MessageId")
            logger.info(f"Successfully published message to SQS: {sqs_message_id}")
            
            return message_id
            
        except ClientError as e:
            logger.error(f"Failed to publish message to SQS: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing message: {e}")
            raise
    
    def publish_error_message(
        self,
        source_image_uri: str,
        error_message: str,
        error_type: str = "OCRProcessingError"
    ) -> str:
        """
        Publish an error message to a dead-letter queue or error topic.
        
        Args:
            source_image_uri: S3 URI of the source image that failed
            error_message: Error description
            error_type: Type of error
        
        Returns:
            Message ID of the published error message
        
        Raises:
            ClientError: If SQS publish operation fails
        """
        try:
            message_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            
            error_payload = {
                "message_id": message_id,
                "timestamp": timestamp,
                "error_type": error_type,
                "error_message": error_message,
                "source_image": {
                    "s3_uri": source_image_uri
                }
            }
            
            message_body = json.dumps(error_payload, ensure_ascii=False)
            
            logger.warning(f"Publishing error message for {source_image_uri}: {error_message}")
            
            response = self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body
            )
            
            sqs_message_id = response.get("MessageId")
            logger.info(f"Successfully published error message to SQS: {sqs_message_id}")
            
            return message_id
            
        except ClientError as e:
            logger.error(f"Failed to publish error message to SQS: {e}")
            raise
