"""SQS consumer for receiving GEDCOM ready messages."""
import json
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SQSConsumer:
    """Consumer for AWS SQS messages."""
    
    def __init__(
        self,
        aws_config: dict,
        queue_url: str,
        max_messages: int = 1,
        wait_time_seconds: int = 20,
        visibility_timeout: int = 300
    ):
        """
        Initialize SQS consumer.
        
        Args:
            aws_config: AWS configuration dictionary for boto3
            queue_url: SQS queue URL
            max_messages: Maximum number of messages to receive per poll (1-10)
            wait_time_seconds: Long polling wait time in seconds (0-20)
            visibility_timeout: Message visibility timeout in seconds
        """
        self.queue_url = queue_url
        self.max_messages = min(max_messages, 10)  # AWS limit is 10
        self.wait_time_seconds = min(wait_time_seconds, 20)  # AWS limit is 20
        self.visibility_timeout = visibility_timeout
        
        # Create SQS client
        self.sqs_client = boto3.client("sqs", **aws_config)
        
        logger.info(
            f"SQSConsumer initialized - Queue: {queue_url}, "
            f"Max messages: {max_messages}, Wait time: {wait_time_seconds}s"
        )
    
    def receive_messages(self) -> List[Dict[str, Any]]:
        """
        Poll SQS queue for messages using long polling.
        
        Returns:
            List of message dictionaries
        
        Raises:
            ClientError: If SQS operation fails
        """
        try:
            logger.debug(f"Polling SQS queue: {self.queue_url}")
            
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=self.max_messages,
                WaitTimeSeconds=self.wait_time_seconds,
                VisibilityTimeout=self.visibility_timeout,
                AttributeNames=["All"],
                MessageAttributeNames=["All"]
            )
            
            messages = response.get("Messages", [])
            
            if messages:
                logger.info(f"Received {len(messages)} message(s) from SQS")
            else:
                logger.debug("No messages received from SQS")
            
            return messages
            
        except ClientError as e:
            logger.error(f"Failed to receive messages from SQS: {e}", exc_info=True)
            raise
    
    def parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SQS message and extract GEDCOM data.
        
        Args:
            message: Raw SQS message dictionary
        
        Returns:
            Parsed message data with gedcom_data, document_metadata, etc.
        
        Raises:
            ValueError: If message format is invalid
        """
        try:
            receipt_handle = message.get("ReceiptHandle")
            message_id = message.get("MessageId")
            body = message.get("Body", "{}")
            
            # Parse JSON body
            try:
                body_data = json.loads(body)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in message body: {e}")
            
            # Extract GEDCOM data
            gedcom_data = body_data.get("gedcom_data")
            if not gedcom_data:
                raise ValueError("No gedcom_data found in message body")
            
            # Extract document metadata
            document_metadata = body_data.get("document_metadata", {})
            
            parsed = {
                "message_id": message_id,
                "receipt_handle": receipt_handle,
                "gedcom_data": gedcom_data,
                "document_metadata": document_metadata,
                "source_ocr_uris": body_data.get("source_ocr_uris", []),
                "metadata": body_data.get("metadata", {}),
                "body": body_data
            }
            
            logger.info(
                f"Parsed message {message_id}: "
                f"document_id={document_metadata.get('document_id')}, "
                f"filename={gedcom_data.get('filename')}"
            )
            
            return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse message: {e}", exc_info=True)
            raise
    
    def delete_message(self, receipt_handle: str) -> None:
        """
        Delete a message from the queue after successful processing.
        
        Args:
            receipt_handle: Receipt handle of the message to delete
        
        Raises:
            ClientError: If deletion fails
        """
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            logger.info("Message deleted from queue")
            
        except ClientError as e:
            logger.error(f"Failed to delete message: {e}", exc_info=True)
            raise
