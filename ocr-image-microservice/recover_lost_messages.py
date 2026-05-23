#!/usr/bin/env python3
"""
Recovery Script for Lost OCR Processing Messages
=================================================

This script scans the S3 input bucket for images that were uploaded but never
processed by the OCR microservice. It identifies unprocessed images by checking
if corresponding OCR results exist in the output bucket, then reconstructs and
resends the appropriate SQS messages.

Usage:
    # Dry run (preview what would be sent)
    python recover_lost_messages.py --dry-run

    # Actually send messages
    python recover_lost_messages.py

    # Filter by S3 prefix
    python recover_lost_messages.py --prefix documents/book-123/

    # Limit number of messages
    python recover_lost_messages.py --max-messages 100

    # Custom batch size for sending
    python recover_lost_messages.py --batch-size 5

    # Verbose output
    python recover_lost_messages.py --verbose

Environment Variables:
    Required (same as ocr-image-microservice):
    - AWS_REGION: AWS region
    - AWS_ACCESS_KEY_ID: AWS access key (optional with IAM roles)
    - AWS_SECRET_ACCESS_KEY: AWS secret key (optional with IAM roles)
    - S3_INPUT_BUCKET: S3 input bucket name
    - S3_OUTPUT_BUCKET: S3 output bucket name
    - IMAGE_UPLOAD_QUEUE_URL: SQS queue URL for image processing
    
    Optional:
    - S3_OUTPUT_PREFIX: S3 output prefix (default: "ocr-results/")
    - SUPPORTED_EXTENSIONS: Comma-separated image extensions (default: jpg,jpeg,png,tiff,tif)

Author: Recovery Script Generator
Version: 1.0.0
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from dotenv import load_dotenv


class RecoveryScriptConfig:
    """Configuration for the recovery script."""
    
    def __init__(self):
        """Load configuration from environment variables."""
        # Load .env file if it exists
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
        
        # Required configuration
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.s3_input_bucket = os.getenv("S3_INPUT_BUCKET")
        self.s3_output_bucket = os.getenv("S3_OUTPUT_BUCKET")
        self.queue_url = os.getenv("IMAGE_UPLOAD_QUEUE_URL")
        
        # Optional configuration
        self.s3_output_prefix = os.getenv("S3_OUTPUT_PREFIX", "ocr-results/")
        if self.s3_output_prefix and not self.s3_output_prefix.endswith("/"):
            self.s3_output_prefix += "/"
        
        # Supported extensions
        extensions_str = os.getenv(
            "SUPPORTED_EXTENSIONS",
            "jpg,jpeg,png,tiff,tif"
        )
        self.supported_extensions = [
            f".{ext.strip().lower()}" for ext in extensions_str.split(",")
        ]
        
        # Validate required configuration
        if not self.s3_input_bucket:
            raise ValueError("S3_INPUT_BUCKET environment variable is required")
        if not self.s3_output_bucket:
            raise ValueError("S3_OUTPUT_BUCKET environment variable is required")
        if not self.queue_url:
            raise ValueError("IMAGE_UPLOAD_QUEUE_URL environment variable is required")
        
        # Detect FIFO queue
        self.is_fifo_queue = self.queue_url.endswith(".fifo")


class S3Scanner:
    """Scans S3 buckets for images and OCR results."""
    
    def __init__(self, config: RecoveryScriptConfig):
        """Initialize the S3 scanner.
        
        Args:
            config: Recovery script configuration
        """
        self.config = config
        
        # Configure boto3 client
        boto_config = BotoConfig(
            region_name=config.aws_region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        
        # Create S3 client
        session_kwargs = {}
        if config.aws_access_key_id and config.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = config.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = config.aws_secret_access_key
        
        session = boto3.Session(**session_kwargs)
        self.s3_client = session.client("s3", config=boto_config)
    
    def scan_input_bucket(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Scan S3 input bucket for image files.
        
        Args:
            prefix: Optional S3 prefix to filter objects
            limit: Optional maximum number of objects to return
            
        Returns:
            List of S3 object keys (image files)
        """
        scan_prefix = prefix if prefix else ""
        
        print(f"Scanning S3 input bucket: s3://{self.config.s3_input_bucket}/{scan_prefix}")
        
        image_keys = []
        paginator = self.s3_client.get_paginator("list_objects_v2")
        
        try:
            page_iterator = paginator.paginate(
                Bucket=self.config.s3_input_bucket,
                Prefix=scan_prefix,
            )
            
            for page in page_iterator:
                if "Contents" not in page:
                    continue
                
                for obj in page["Contents"]:
                    # Check if limit reached
                    if limit and len(image_keys) >= limit:
                        print(f"Reached limit of {limit} objects")
                        return image_keys
                    
                    # Filter by extension
                    key = obj["Key"]
                    if any(key.lower().endswith(ext) for ext in self.config.supported_extensions):
                        image_keys.append(key)
            
            print(f"Found {len(image_keys)} images")
            return image_keys
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"Error scanning input bucket: {error_code} - {e}")
            raise
    
    def get_processed_images(
        self,
        prefix: Optional[str] = None,
    ) -> Set[str]:
        """Get set of images that have been processed (have OCR results).
        
        Args:
            prefix: Optional S3 prefix to filter objects
            
        Returns:
            Set of original image keys that have been processed
        """
        # Construct the output prefix to scan
        if prefix:
            scan_prefix = f"{self.config.s3_output_prefix}{prefix}"
        else:
            scan_prefix = self.config.s3_output_prefix
        
        print(f"Checking processed images in: s3://{self.config.s3_output_bucket}/{scan_prefix}")
        
        processed_keys = set()
        paginator = self.s3_client.get_paginator("list_objects_v2")
        
        try:
            page_iterator = paginator.paginate(
                Bucket=self.config.s3_output_bucket,
                Prefix=scan_prefix,
            )
            
            for page in page_iterator:
                if "Contents" not in page:
                    continue
                
                for obj in page["Contents"]:
                    key = obj["Key"]
                    
                    # Skip if not a markdown file
                    if not key.endswith(".md"):
                        continue
                    
                    # Convert output key back to original image key
                    # Remove output prefix and .md extension
                    relative_key = key[len(self.config.s3_output_prefix):]
                    
                    # Remove .md extension and try to match with supported image extensions
                    base_key = relative_key[:-3]  # Remove .md
                    
                    # The original image could have any supported extension
                    # We'll store the base key and check against it later
                    processed_keys.add(base_key)
            
            print(f"Found {len(processed_keys)} processed images")
            return processed_keys
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchBucket":
                print(f"Warning: Output bucket does not exist: {self.config.s3_output_bucket}")
                return set()
            print(f"Error scanning output bucket: {error_code} - {e}")
            raise
    
    def is_image_processed(self, image_key: str, processed_keys: Set[str]) -> bool:
        """Check if an image has been processed.
        
        Args:
            image_key: S3 key of the image
            processed_keys: Set of processed base keys (without extension)
            
        Returns:
            True if the image has been processed, False otherwise
        """
        # Get the base key without extension
        base_key = str(Path(image_key).with_suffix(""))
        return base_key in processed_keys


class MessageReconstructor:
    """Reconstructs SQS messages for unprocessed images."""
    
    def __init__(self, config: RecoveryScriptConfig):
        """Initialize the message reconstructor.
        
        Args:
            config: Recovery script configuration
        """
        self.config = config
    
    def reconstruct_message(self, image_key: str) -> Dict:
        """Reconstruct SQS message body for an unprocessed image.
        
        Args:
            image_key: S3 key of the image
            
        Returns:
            Message body dictionary matching the microservice format
        """
        # Construct S3 URI
        s3_uri = f"s3://{self.config.s3_input_bucket}/{image_key}"
        
        # Build message body (simple format expected by OCR microservice)
        message = {
            "s3_uri": s3_uri,
        }
        
        return message


class SQSMessageSender:
    """Sends reconstructed messages to SQS queue."""
    
    def __init__(self, config: RecoveryScriptConfig):
        """Initialize the SQS sender.
        
        Args:
            config: Recovery script configuration
        """
        self.config = config
        
        # Configure boto3 client
        boto_config = BotoConfig(
            region_name=config.aws_region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )
        
        # Create SQS client
        session_kwargs = {}
        if config.aws_access_key_id and config.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = config.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = config.aws_secret_access_key
        
        session = boto3.Session(**session_kwargs)
        self.sqs_client = session.client("sqs", config=boto_config)
    
    def send_message(
        self,
        message_body: Dict,
        dry_run: bool = False,
    ) -> Optional[str]:
        """Send a message to the SQS queue.
        
        Args:
            message_body: Message body dictionary
            dry_run: If True, don't actually send the message
            
        Returns:
            Message ID if sent, None if dry run
        """
        if dry_run:
            print(f"[DRY RUN] Would send message for: {message_body['s3_uri']}")
            return None
        
        # Prepare base send_message parameters
        send_params = {
            "QueueUrl": self.config.queue_url,
            "MessageBody": json.dumps(message_body),
        }
        
        # Add FIFO-specific parameters if needed
        if self.config.is_fifo_queue:
            # MessageGroupId: Group related messages together
            message_group_id = "ocr-recovery"
            
            # MessageDeduplicationId: Prevent duplicate messages
            # Hash the S3 URI for deduplication
            s3_uri = message_body["s3_uri"]
            message_deduplication_id = hashlib.sha256(s3_uri.encode()).hexdigest()
            
            send_params["MessageGroupId"] = message_group_id
            send_params["MessageDeduplicationId"] = message_deduplication_id
        
        try:
            response = self.sqs_client.send_message(**send_params)
            message_id = response.get("MessageId", "")
            print(f"✓ Sent message {message_id} for: {message_body['s3_uri']}")
            return message_id
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"✗ Error sending message for {message_body['s3_uri']}: {error_code} - {e}")
            return None
    
    def send_messages_batch(
        self,
        messages: List[Dict],
        dry_run: bool = False,
    ) -> int:
        """Send multiple messages in batches.
        
        Args:
            messages: List of message body dictionaries
            dry_run: If True, don't actually send messages
            
        Returns:
            Number of messages sent successfully
        """
        success_count = 0
        
        for message_body in messages:
            message_id = self.send_message(message_body, dry_run)
            if message_id or dry_run:
                success_count += 1
        
        return success_count


def main():
    """Main entry point for the recovery script."""
    parser = argparse.ArgumentParser(
        description="Recover lost OCR processing messages by scanning S3 buckets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview what would be sent
  python recover_lost_messages.py --dry-run

  # Actually send messages
  python recover_lost_messages.py

  # Filter by S3 prefix
  python recover_lost_messages.py --prefix documents/book-123/

  # Limit number of messages
  python recover_lost_messages.py --max-messages 100

  # Custom batch size
  python recover_lost_messages.py --batch-size 5

  # Verbose output with dry run
  python recover_lost_messages.py --dry-run --verbose
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be sent without actually sending messages"
    )
    
    parser.add_argument(
        "--prefix",
        type=str,
        help="S3 prefix to filter objects (e.g., 'documents/book-123/')"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of messages to send per batch (default: 10)"
    )
    
    parser.add_argument(
        "--max-messages",
        type=int,
        help="Maximum number of messages to regenerate (optional limit)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print("=" * 70)
    print("OCR Image Microservice - Message Recovery Script")
    print("=" * 70)
    print()
    
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No messages will be sent")
        print()
    
    try:
        # Load configuration
        print("Loading configuration...")
        config = RecoveryScriptConfig()
        print(f"  S3 Input Bucket: {config.s3_input_bucket}")
        print(f"  S3 Output Bucket: {config.s3_output_bucket}")
        print(f"  S3 Output Prefix: {config.s3_output_prefix}")
        print(f"  SQS Queue: {config.queue_url}")
        print(f"  FIFO Queue: {config.is_fifo_queue}")
        print(f"  Supported Extensions: {', '.join(config.supported_extensions)}")
        print()
        
        # Initialize components
        scanner = S3Scanner(config)
        reconstructor = MessageReconstructor(config)
        sender = SQSMessageSender(config)
        
        # Step 1: Scan input bucket for all images
        print("Step 1: Scanning input bucket for images...")
        image_keys = scanner.scan_input_bucket(
            prefix=args.prefix,
            limit=None,  # Don't limit scanning, only limit message sending
        )
        
        if not image_keys:
            print("No images found matching the criteria.")
            return 0
        
        print()
        
        # Step 2: Get list of processed images
        print("Step 2: Checking processing status...")
        processed_keys = scanner.get_processed_images(prefix=args.prefix)
        
        print()
        
        # Step 3: Identify unprocessed images
        print("Step 3: Identifying unprocessed images...")
        unprocessed_images = []
        
        for image_key in image_keys:
            if not scanner.is_image_processed(image_key, processed_keys):
                unprocessed_images.append(image_key)
                if args.verbose:
                    print(f"  Unprocessed: {image_key}")
        
        already_processed = len(image_keys) - len(unprocessed_images)
        
        print(f"- Total images scanned: {len(image_keys)}")
        print(f"- Already processed: {already_processed}")
        print(f"- Unprocessed: {len(unprocessed_images)}")
        print()
        
        if not unprocessed_images:
            print("All images have been processed. No messages to regenerate.")
            return 0
        
        # Apply max-messages limit if specified
        if args.max_messages and len(unprocessed_images) > args.max_messages:
            print(f"Limiting to {args.max_messages} messages (out of {len(unprocessed_images)} unprocessed)")
            unprocessed_images = unprocessed_images[:args.max_messages]
            print()
        
        # Step 4: Regenerate messages
        print(f"Step 4: Regenerating messages for {len(unprocessed_images)} images...")
        print()
        
        success_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, len(unprocessed_images), args.batch_size):
            batch = unprocessed_images[i:i + args.batch_size]
            
            if args.verbose:
                print(f"Processing batch {i // args.batch_size + 1} ({len(batch)} images)...")
            
            for image_key in batch:
                try:
                    # Reconstruct message
                    message_body = reconstructor.reconstruct_message(image_key)
                    
                    if args.verbose and args.dry_run:
                        print(f"  Message: {json.dumps(message_body)}")
                    
                    # Send message
                    message_id = sender.send_message(
                        message_body=message_body,
                        dry_run=args.dry_run,
                    )
                    
                    if message_id or args.dry_run:
                        success_count += 1
                    else:
                        error_count += 1
                    
                except Exception as e:
                    print(f"✗ Error processing {image_key}: {e}")
                    error_count += 1
                    if args.verbose:
                        import traceback
                        traceback.print_exc()
        
        # Print summary
        print()
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Total images scanned: {len(image_keys)}")
        print(f"Already processed: {already_processed}")
        print(f"Messages regenerated: {success_count}")
        if error_count > 0:
            print(f"Errors: {error_count}")
        
        if args.dry_run:
            print()
            print("⚠️  This was a DRY RUN - no messages were actually sent")
            print("Run without --dry-run to send messages to the queue")
        
        print()
        
        return 0 if error_count == 0 else 1
        
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        return 130
        
    except Exception as e:
        print(f"Fatal error: {e}")
        if args.verbose if 'args' in locals() else False:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
