"""SQS consumer for receiving OCR processing messages."""
import json
import re
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
        
        # Extract region from queue URL for diagnostics
        queue_region = self._extract_region_from_queue_url(queue_url)
        configured_region = aws_config.get("region_name", "unknown")
        
        # Log diagnostic information
        logger.info(
            f"SQSConsumer initialized - Queue: {queue_url}, "
            f"Max messages: {max_messages}, Wait time: {wait_time_seconds}s"
        )
        logger.info(f"DIAGNOSTIC - Configured AWS Region: {configured_region}")
        logger.info(f"DIAGNOSTIC - Queue URL Region: {queue_region}")
        
        # Check for region mismatch
        if queue_region and queue_region != configured_region:
            logger.error(
                f"REGION MISMATCH DETECTED! "
                f"AWS_REGION is set to '{configured_region}' but the SQS queue "
                f"is in region '{queue_region}'. This will cause 'QueueDoesNotExist' errors. "
                f"Please update AWS_REGION in your .env file to match the queue region."
            )
        
        # Create SQS client
        self.sqs_client = boto3.client("sqs", **aws_config)
    
    def receive_messages(self) -> List[Dict[str, Any]]:
        """
        Poll SQS queue for messages using long polling.
        
        Returns:
            List of message dictionaries
        
        Raises:
            ClientError: If SQS operation fails
        """
        try:
            logger.info(f"DIAGNOSTIC - receive_messages: Polling SQS queue: {self.queue_url}")
            logger.info(f"DIAGNOSTIC - receive_messages: MaxMessages={self.max_messages}, WaitTime={self.wait_time_seconds}s")
            
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=self.max_messages,
                WaitTimeSeconds=self.wait_time_seconds,
                VisibilityTimeout=self.visibility_timeout,
                AttributeNames=["All"],
                MessageAttributeNames=["All"]
            )
            
            logger.info(f"DIAGNOSTIC - receive_messages: SQS API call completed successfully")
            logger.info(f"DIAGNOSTIC - receive_messages: Response keys: {list(response.keys())}")
            
            messages = response.get("Messages", [])
            
            if messages:
                logger.info(f"DIAGNOSTIC - receive_messages: Received {len(messages)} message(s) from SQS")
            else:
                logger.info("DIAGNOSTIC - receive_messages: No messages received from SQS (empty queue or no new messages)")
            
            return messages
            
        except ClientError as e:
            logger.error(f"DIAGNOSTIC - receive_messages: ClientError occurred: {e}", exc_info=True)
            logger.error(f"DIAGNOSTIC - receive_messages: Error code: {e.response.get('Error', {}).get('Code', 'Unknown')}")
            logger.error(f"DIAGNOSTIC - receive_messages: Error message: {e.response.get('Error', {}).get('Message', 'Unknown')}")
            raise
        except Exception as e:
            logger.error(f"DIAGNOSTIC - receive_messages: Unexpected exception: {e}", exc_info=True)
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
            
            # DIAGNOSTIC: Log raw message body before parsing
            logger.info(f"DIAGNOSTIC - Raw message body (first 500 chars): {body[:500]}")
            
            # Parse JSON body
            try:
                body_data = json.loads(body)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in message body: {e}")
            
            # DIAGNOSTIC: Log the entire message body structure
            logger.info(f"DIAGNOSTIC - Message body keys: {list(body_data.keys())}")
            logger.info(f"DIAGNOSTIC - Full message body (pretty printed): {json.dumps(body_data, indent=2)}")
            
            # DIAGNOSTIC: Check if this is an S3 Event Notification format
            if "Records" in body_data:
                logger.info("DIAGNOSTIC - Detected S3 Event Notification format (has 'Records' key)")
                if body_data.get("Records"):
                    first_record = body_data["Records"][0]
                    logger.info(f"DIAGNOSTIC - First record keys: {list(first_record.keys())}")
                    if "s3" in first_record:
                        s3_data = first_record["s3"]
                        logger.info(f"DIAGNOSTIC - S3 data: {json.dumps(s3_data, indent=2)}")
                        if "bucket" in s3_data:
                            logger.info(f"DIAGNOSTIC - Bucket info: {s3_data['bucket']}")
                        if "object" in s3_data:
                            logger.info(f"DIAGNOSTIC - Object info: {s3_data['object']}")
            
            # Check if this is an S3 Event Notification (standard AWS format)
            if "Records" in body_data and body_data.get("Records"):
                logger.info("DIAGNOSTIC - Processing as S3 Event Notification format")
                record = body_data["Records"][0]
                s3_info = record.get("s3", {})
                bucket_name = s3_info.get("bucket", {}).get("name")
                object_key = s3_info.get("object", {}).get("key")
                
                if bucket_name and object_key:
                    s3_uri = f"s3://{bucket_name}/{object_key}"
                    logger.info(f"DIAGNOSTIC - Constructed S3 URI from S3 Event: {s3_uri}")
                else:
                    logger.error(f"DIAGNOSTIC - S3 Event missing bucket or object: bucket={bucket_name}, key={object_key}")
                    raise ValueError("S3 Event Notification missing bucket name or object key")
            else:
                # Extract S3 URI (support multiple possible field names for custom format)
                logger.info("DIAGNOSTIC - Processing as custom message format")
                s3_uri = (
                    body_data.get("s3_uri") or
                    body_data.get("s3Uri") or
                    body_data.get("imageUri") or
                    body_data.get("image_uri")
                )
                
                if not s3_uri:
                    logger.error(f"DIAGNOSTIC - No S3 URI field found. Available fields: {list(body_data.keys())}")
                    raise ValueError("No S3 URI found in message body")
                
                # DIAGNOSTIC: Log what URI format was found and from which field
                for field in ["s3_uri", "s3Uri", "imageUri", "image_uri"]:
                    if body_data.get(field):
                        logger.info(f"DIAGNOSTIC - S3 URI extracted from field '{field}': {body_data.get(field)}")
            
            # DIAGNOSTIC: Check if the extracted URI is an ARN
            if s3_uri.startswith("arn:aws:s3"):
                logger.error(f"DIAGNOSTIC - DETECTED ARN FORMAT (NOT s3:// URI): {s3_uri}")
                logger.error("DIAGNOSTIC - ARNs cannot be used directly with boto3 download operations")
                logger.error("DIAGNOSTIC - The message format may be incorrect or needs ARN parsing")
            
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
