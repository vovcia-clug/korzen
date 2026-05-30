"""SQS consumer for receiving OCR result messages."""
import json
import re
from typing import Optional, List, Dict, Any
import aioboto3
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
        self.aws_config = aws_config
        
        # Create aioboto3 session (client opened lazily inside each async method)
        self.session = aioboto3.Session()
        
        # Extract region from queue URL for diagnostics
        queue_region = self._extract_region_from_queue_url(queue_url)
        configured_region = aws_config.get("region_name", "unknown")
        
        # Log diagnostic information
        logger.info(
            f"SQSConsumer initialized - Queue: {queue_url}, "
            f"Max messages: {max_messages}, Wait time: {wait_time_seconds}s"
        )
        logger.info(f"Configured AWS Region: {configured_region}")
        logger.info(f"Queue URL Region: {queue_region}")
        
        # Check for region mismatch
        if queue_region and queue_region != configured_region:
            logger.error(
                f"REGION MISMATCH DETECTED! "
                f"AWS_REGION is set to '{configured_region}' but the SQS queue "
                f"is in region '{queue_region}'. This will cause 'QueueDoesNotExist' errors. "
                f"Please update AWS_REGION in your .env file to match the queue region."
            )
    
    async def receive_messages(self) -> List[Dict[str, Any]]:
        """
        Poll SQS queue for messages using long polling.
        
        Returns:
            List of message dictionaries
        
        Raises:
            ClientError: If SQS operation fails
        """
        try:
            logger.debug(f"Polling SQS queue: {self.queue_url}")
            
            async with self.session.client("sqs", **self.aws_config) as client:
                response = await client.receive_message(
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
            logger.error(f"ClientError occurred: {e}", exc_info=True)
            logger.error(f"Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
            logger.error(f"Error message: {e.response.get('Error', {}).get('Message', 'Unknown')}")
            raise
        except Exception as e:
            logger.error(f"Unexpected exception: {e}", exc_info=True)
            raise
    
    def parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SQS message and extract OCR result data.
        
        Args:
            message: Raw SQS message dictionary
        
        Returns:
            Parsed message data with metadata, ocr_result, etc.
        
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
            
            # Validate required fields
            if "metadata" not in body_data:
                raise ValueError("Missing 'metadata' field in message")
            if "ocr_result" not in body_data:
                raise ValueError("Missing 'ocr_result' field in message")
            
            metadata = body_data["metadata"]
            if "document_id" not in metadata:
                raise ValueError("Missing 'document_id' in metadata")
            
            # page_number is optional - some documents may be single-page
            # or page number may not be extractable from filename/path
            if "page_number" not in metadata:
                logger.warning(
                    f"Message {message_id} missing 'page_number' in metadata. "
                    f"Treating as single-page document or page number unknown."
                )
                metadata["page_number"] = None
            
            parsed = {
                "message_id": message_id,
                "receipt_handle": receipt_handle,
                "body": body_data,
                "metadata": metadata,
                "ocr_result": body_data["ocr_result"],
                "attributes": message.get("Attributes", {}),
                "message_attributes": message.get("MessageAttributes", {})
            }
            
            logger.info(
                f"Parsed message {message_id}: document_id={metadata['document_id']}, "
                f"page={metadata['page_number']}"
            )
            return parsed
            
        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            raise ValueError(f"Message parsing failed: {e}")
    
    async def delete_message(self, receipt_handle: str) -> None:
        """
        Delete a message from the SQS queue after successful processing.
        
        Args:
            receipt_handle: Receipt handle of the message to delete
        
        Raises:
            ClientError: If SQS delete operation fails
        """
        try:
            logger.debug(f"Deleting message from SQS")
            
            async with self.session.client("sqs", **self.aws_config) as client:
                await client.delete_message(
                    QueueUrl=self.queue_url,
                    ReceiptHandle=receipt_handle
                )
            
            logger.debug("Message deleted successfully")
            
        except ClientError as e:
            logger.error(f"Failed to delete message from SQS: {e}")
            raise
    
    async def change_message_visibility(
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
            async with self.session.client("sqs", **self.aws_config) as client:
                await client.change_message_visibility(
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
    
    @staticmethod
    def _extract_region_from_queue_url(queue_url: str) -> Optional[str]:
        """
        Extract AWS region from SQS queue URL.
        
        SQS queue URLs have the format:
        https://sqs.{region}.amazonaws.com/{account-id}/{queue-name}
        
        Args:
            queue_url: SQS queue URL
            
        Returns:
            Region string or None if not found
        """
        match = re.search(r'sqs\.([a-z0-9-]+)\.amazonaws\.com', queue_url)
        if match:
            return match.group(1)
        return None
