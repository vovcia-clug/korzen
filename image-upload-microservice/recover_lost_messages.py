#!/usr/bin/env python3
"""
Recovery Script for Lost SQS Messages
======================================

This script scans an S3 bucket for images that were uploaded but their SQS
messages were lost. It reconstructs and resends the appropriate messages to
the queue, matching the format used by the image-upload-microservice.

Usage:
    # Dry run (preview what would be sent)
    python recover_lost_messages.py --dry-run

    # Actually send messages
    python recover_lost_messages.py

    # Filter by date range
    python recover_lost_messages.py --start-date 2026-05-01 --end-date 2026-05-23

    # Filter by S3 prefix
    python recover_lost_messages.py --prefix uploads/2026/05/

    # Limit number of messages
    python recover_lost_messages.py --limit 100

    # Verbose output
    python recover_lost_messages.py --verbose

Environment Variables:
    Required (same as image-upload-microservice):
    - AWS_REGION: AWS region
    - AWS_ACCESS_KEY_ID: AWS access key (optional with IAM roles)
    - AWS_SECRET_ACCESS_KEY: AWS secret key (optional with IAM roles)
    - S3_INPUT_BUCKET: S3 bucket name
    - IMAGE_UPLOAD_QUEUE_URL: SQS queue URL

    Optional:
    - S3_INPUT_PREFIX: S3 object key prefix (default: "")
    - SUPPORTED_EXTENSIONS: Comma-separated image extensions (default: jpg,jpeg,png,gif,bmp,tiff,tif,webp)

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
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Try to import PIL for image metadata extraction
try:
    from PIL import Image
    from io import BytesIO
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL/Pillow not available. Image dimensions will not be extracted.")


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
        self.s3_bucket = os.getenv("S3_INPUT_BUCKET")
        self.queue_url = os.getenv("IMAGE_UPLOAD_QUEUE_URL")
        
        # Optional configuration
        self.s3_prefix = os.getenv("S3_INPUT_PREFIX", "")
        if self.s3_prefix and not self.s3_prefix.endswith("/"):
            self.s3_prefix += "/"
        
        # Supported extensions
        extensions_str = os.getenv(
            "SUPPORTED_EXTENSIONS",
            "jpg,jpeg,png,gif,bmp,tiff,tif,webp"
        )
        self.supported_extensions = [
            f".{ext.strip().lower()}" for ext in extensions_str.split(",")
        ]
        
        # Validate required configuration
        if not self.s3_bucket:
            raise ValueError("S3_INPUT_BUCKET environment variable is required")
        if not self.queue_url:
            raise ValueError("IMAGE_UPLOAD_QUEUE_URL environment variable is required")
        
        # Detect FIFO queue
        self.is_fifo_queue = self.queue_url.endswith(".fifo")


class S3ImageScanner:
    """Scans S3 bucket for image objects."""
    
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
    
    def scan_bucket(
        self,
        prefix: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Scan S3 bucket for image objects.
        
        Args:
            prefix: Optional S3 prefix to filter objects
            start_date: Optional start date filter (based on LastModified)
            end_date: Optional end date filter (based on LastModified)
            limit: Optional maximum number of objects to return
            
        Returns:
            List of S3 object metadata dictionaries
        """
        # Determine the prefix to use
        scan_prefix = prefix if prefix else self.config.s3_prefix
        
        print(f"Scanning S3 bucket: s3://{self.config.s3_bucket}/{scan_prefix}")
        if start_date:
            print(f"  Start date filter: {start_date.isoformat()}")
        if end_date:
            print(f"  End date filter: {end_date.isoformat()}")
        if limit:
            print(f"  Limit: {limit} objects")
        
        objects = []
        paginator = self.s3_client.get_paginator("list_objects_v2")
        
        try:
            page_iterator = paginator.paginate(
                Bucket=self.config.s3_bucket,
                Prefix=scan_prefix,
            )
            
            for page in page_iterator:
                if "Contents" not in page:
                    continue
                
                for obj in page["Contents"]:
                    # Check if limit reached
                    if limit and len(objects) >= limit:
                        print(f"Reached limit of {limit} objects")
                        return objects
                    
                    # Filter by extension
                    key = obj["Key"]
                    if not any(key.lower().endswith(ext) for ext in self.config.supported_extensions):
                        continue
                    
                    # Filter by date
                    last_modified = obj["LastModified"]
                    if start_date and last_modified < start_date.replace(tzinfo=timezone.utc):
                        continue
                    if end_date and last_modified > end_date.replace(tzinfo=timezone.utc):
                        continue
                    
                    objects.append(obj)
            
            print(f"Found {len(objects)} image objects")
            return objects
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"Error scanning bucket: {error_code} - {e}")
            raise
    
    def get_object_metadata(self, s3_key: str) -> Dict:
        """Get detailed metadata for an S3 object.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Dictionary with object metadata
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.config.s3_bucket,
                Key=s3_key,
            )
            
            metadata = {
                "content_type": response.get("ContentType", "application/octet-stream"),
                "content_length": response.get("ContentLength", 0),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "s3_metadata": response.get("Metadata", {}),
            }
            
            return metadata
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"Error getting metadata for {s3_key}: {error_code} - {e}")
            return {}
    
    def get_image_dimensions(self, s3_key: str) -> Optional[Dict[str, int]]:
        """Extract image dimensions from S3 object.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Dictionary with width and height, or None if extraction fails
        """
        if not HAS_PIL:
            return None
        
        try:
            # Download only the first 64KB to extract dimensions
            response = self.s3_client.get_object(
                Bucket=self.config.s3_bucket,
                Key=s3_key,
                Range="bytes=0-65535"
            )
            
            image_data = response["Body"].read()
            image = Image.open(BytesIO(image_data))
            
            return {
                "width": image.width,
                "height": image.height,
            }
            
        except Exception as e:
            print(f"Warning: Could not extract dimensions for {s3_key}: {e}")
            return None


class MessageReconstructor:
    """Reconstructs SQS messages from S3 object metadata."""
    
    def __init__(self, config: RecoveryScriptConfig):
        """Initialize the message reconstructor.
        
        Args:
            config: Recovery script configuration
        """
        self.config = config
    
    def reconstruct_message(
        self,
        s3_key: str,
        s3_metadata: Dict,
        image_dimensions: Optional[Dict[str, int]] = None,
    ) -> Dict:
        """Reconstruct SQS message body from S3 object metadata.
        
        Args:
            s3_key: S3 object key
            s3_metadata: S3 object metadata
            image_dimensions: Optional image dimensions
            
        Returns:
            Message body dictionary matching the microservice format
        """
        # Extract original filename from S3 key or metadata
        original_filename = s3_metadata.get("s3_metadata", {}).get(
            "original-filename",
            Path(s3_key).name
        )
        
        # Construct S3 URI
        s3_uri = f"s3://{self.config.s3_bucket}/{s3_key}"
        
        # Build metadata section
        metadata = {
            "original_filename": original_filename,
            "upload_timestamp": datetime.now(timezone.utc).isoformat(),
            "file_size_bytes": s3_metadata.get("content_length", 0),
            "content_type": s3_metadata.get("content_type", "application/octet-stream"),
        }
        
        # Add image dimensions if available
        if image_dimensions:
            metadata["image_dimensions"] = image_dimensions
        elif "image-width" in s3_metadata.get("s3_metadata", {}):
            # Try to get from S3 metadata
            try:
                metadata["image_dimensions"] = {
                    "width": int(s3_metadata["s3_metadata"]["image-width"]),
                    "height": int(s3_metadata["s3_metadata"]["image-height"]),
                }
            except (ValueError, KeyError):
                pass
        
        # Add file hash if available in S3 metadata
        if "file-hash" in s3_metadata.get("s3_metadata", {}):
            metadata["file_hash"] = {
                "value": s3_metadata["s3_metadata"]["file-hash"],
                "algorithm": s3_metadata["s3_metadata"].get("hash-algorithm", "sha256"),
            }
        
        # Add image format if available
        if "image-format" in s3_metadata.get("s3_metadata", {}):
            metadata["image_format"] = s3_metadata["s3_metadata"]["image-format"]
        else:
            # Infer from extension
            ext = Path(s3_key).suffix.lower().lstrip(".")
            if ext == "jpg":
                ext = "jpeg"
            metadata["image_format"] = ext.upper()
        
        # Check for JSON metadata URI
        if "json-metadata-uri" in s3_metadata.get("s3_metadata", {}):
            metadata["json_metadata_s3_uri"] = s3_metadata["s3_metadata"]["json-metadata-uri"]
        
        # Construct message body (matching the microservice format)
        message = {
            "s3_uri": s3_uri,
            "metadata": metadata,
            "source_service": "image-upload-microservice",
            "message_version": "1.0",
        }
        
        return message
    
    def construct_message_attributes(self, metadata: Dict) -> Dict:
        """Construct SQS message attributes.
        
        Args:
            metadata: Message metadata
            
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
        message_attributes: Dict,
        dry_run: bool = False,
    ) -> Optional[str]:
        """Send a message to the SQS queue.
        
        Args:
            message_body: Message body dictionary
            message_attributes: Message attributes dictionary
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
            "MessageAttributes": message_attributes,
        }
        
        # Add FIFO-specific parameters if needed
        if self.config.is_fifo_queue:
            # MessageGroupId: Group related messages together
            message_group_id = "image-uploads-recovery"
            
            # MessageDeduplicationId: Prevent duplicate messages
            # Use file hash if available, otherwise hash the S3 URI
            file_hash = message_body.get("metadata", {}).get("file_hash", {}).get("value", "")
            if file_hash:
                message_deduplication_id = file_hash
            else:
                # Fallback: hash the S3 URI
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


def parse_date(date_str: str) -> datetime:
    """Parse date string in ISO format.
    
    Args:
        date_str: Date string in ISO format (YYYY-MM-DD)
        
    Returns:
        Datetime object
    """
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main():
    """Main entry point for the recovery script."""
    parser = argparse.ArgumentParser(
        description="Recover lost SQS messages for images in S3 bucket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview what would be sent
  python recover_lost_messages.py --dry-run

  # Actually send messages
  python recover_lost_messages.py

  # Filter by date range
  python recover_lost_messages.py --start-date 2026-05-01 --end-date 2026-05-23

  # Filter by S3 prefix
  python recover_lost_messages.py --prefix uploads/2026/05/

  # Limit number of messages
  python recover_lost_messages.py --limit 100

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
        help="S3 prefix to filter objects (overrides S3_INPUT_PREFIX env var)"
    )
    
    parser.add_argument(
        "--start-date",
        type=parse_date,
        help="Start date filter (YYYY-MM-DD, based on S3 LastModified)"
    )
    
    parser.add_argument(
        "--end-date",
        type=parse_date,
        help="End date filter (YYYY-MM-DD, based on S3 LastModified)"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of messages to process"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--extract-dimensions",
        action="store_true",
        default=True,
        help="Extract image dimensions (requires PIL/Pillow, enabled by default)"
    )
    
    parser.add_argument(
        "--no-extract-dimensions",
        action="store_false",
        dest="extract_dimensions",
        help="Skip image dimension extraction"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print("=" * 70)
    print("Image Upload Microservice - Message Recovery Script")
    print("=" * 70)
    print()
    
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No messages will be sent")
        print()
    
    try:
        # Load configuration
        print("Loading configuration...")
        config = RecoveryScriptConfig()
        print(f"  S3 Bucket: {config.s3_bucket}")
        print(f"  S3 Prefix: {config.s3_prefix or '(none)'}")
        print(f"  SQS Queue: {config.queue_url}")
        print(f"  FIFO Queue: {config.is_fifo_queue}")
        print(f"  Supported Extensions: {', '.join(config.supported_extensions)}")
        print()
        
        # Initialize components
        scanner = S3ImageScanner(config)
        reconstructor = MessageReconstructor(config)
        sender = SQSMessageSender(config)
        
        # Scan S3 bucket
        print("Scanning S3 bucket for images...")
        objects = scanner.scan_bucket(
            prefix=args.prefix,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
        )
        
        if not objects:
            print("No images found matching the criteria.")
            return 0
        
        print()
        print(f"Processing {len(objects)} images...")
        print()
        
        # Process each object
        success_count = 0
        error_count = 0
        
        for i, obj in enumerate(objects, 1):
            s3_key = obj["Key"]
            
            if args.verbose:
                print(f"[{i}/{len(objects)}] Processing: {s3_key}")
            
            try:
                # Get detailed metadata
                s3_metadata = scanner.get_object_metadata(s3_key)
                
                # Extract image dimensions if requested
                image_dimensions = None
                if args.extract_dimensions and HAS_PIL:
                    image_dimensions = scanner.get_image_dimensions(s3_key)
                
                # Reconstruct message
                message_body = reconstructor.reconstruct_message(
                    s3_key=s3_key,
                    s3_metadata=s3_metadata,
                    image_dimensions=image_dimensions,
                )
                
                message_attributes = reconstructor.construct_message_attributes(
                    message_body["metadata"]
                )
                
                if args.verbose and args.dry_run:
                    print(f"  Message body: {json.dumps(message_body, indent=2)}")
                
                # Send message
                message_id = sender.send_message(
                    message_body=message_body,
                    message_attributes=message_attributes,
                    dry_run=args.dry_run,
                )
                
                if message_id or args.dry_run:
                    success_count += 1
                else:
                    error_count += 1
                
            except Exception as e:
                print(f"✗ Error processing {s3_key}: {e}")
                error_count += 1
                if args.verbose:
                    import traceback
                    traceback.print_exc()
        
        # Print summary
        print()
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Total images processed: {len(objects)}")
        print(f"Messages sent successfully: {success_count}")
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
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
