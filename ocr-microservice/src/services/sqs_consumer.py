"""SQS consumer for receiving OCR processing messages."""
import json
from typing import Optional, List, Dict, Any
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
            logger.error(f"Failed to receive messages from SQS: {e}")
            raise
    
    def parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SQS message and extract relevant information.
        
        Args:
            message: Raw SQS message dictionary
        
        Returns:
            Parsed message data with s3_uri, receipt_handle, etc.
        
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
            
            # Extract S3 URI (support multiple possible field names)
            s3_uri = (
                body_data.get("s3_uri") or
                body_data.get("s3Uri") or
                body_data.get("imageUri") or
                body_data.get("image_uri")
            )
            
            if not s3_uri:
                raise ValueError("No S3 URI found in message body")
            
            parsed = {
                "message_id": message_id,
                "receipt_handle": receipt_handle,
                "s3_uri": s3_uri,
                "body": body_data,
                "attributes": message.get("Attributes", {}),
                "message_attributes": message.get("MessageAttributes", {})
            }
            
            logger.info(f"Parsed message {message_id}: S3 URI = {s3_uri}")
            return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            raise ValueError(f"Message parsing failed: {e}")
    
    def delete_message(self, receipt_handle: str) -> None:
        """
        Delete a message from the SQS queue after successful processing.
        
        Args:
            receipt_handle: Receipt handle of the message to delete
        
        Raises:
            ClientError: If SQS delete operation fails
        """
        try:
            logger.info(f"Deleting message from SQS")
            
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle
            )
            
            logger.info("Message deleted successfully")
            
        except ClientError as e:
            logger.error(f"Failed to delete message from SQS: {e}")
            raise
    
    def change_message_visibility(
        self,
        receipt_handle: str,
        visibility_timeout: int
    ) -> None:
        """
        Change the visibility timeout of a message.
        
        Useful for extending processing time or making message immediately visible again.
        
        Args:
            receipt_handle: Receipt handle of the message
            visibility_timeout: New visibility timeout in seconds
        
        Raises:
            ClientError: If SQS operation fails
        """
        try:
            self.sqs_client.change_message_visibility(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=visibility_timeout
            )
            
            logger.debug(
                f"Changed message visibility timeout to {visibility_timeout}s"
            )
            
        except ClientError as e:
            logger.error(f"Failed to change message visibility: {e}")
            raise
