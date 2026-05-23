#!/usr/bin/env python3
"""
Forward OCR Results Script
===========================

This script scans the S3 output bucket for OCR results (markdown files) and
sends messages to the OCR_RESULTS_QUEUE for further processing by the GEDCOM
generation microservice. Useful for reprocessing existing OCR results or
recovering from queue message losses.

Usage:
    # Dry run (preview what would be sent)
    python forward_ocr_results.py --dry-run

    # Actually send messages
    python forward_ocr_results.py

    # Filter by S3 prefix
    python forward_ocr_results.py --prefix ocr-results/documents/book-123/

    # Limit number of messages
    python forward_ocr_results.py --max-messages 100

    # Custom batch size for sending
    python forward_ocr_results.py --batch-size 5

    # Verbose output
    python forward_ocr_results.py --verbose

Environment Variables:
    Required:
    - AWS_REGION: AWS region
    - AWS_ACCESS_KEY_ID: AWS access key (optional with IAM roles)
    - AWS_SECRET_ACCESS_KEY: AWS secret key (optional with IAM roles)
    - S3_INPUT_BUCKET: S3 input bucket name (for source images)
    - S3_OUTPUT_BUCKET: S3 output bucket name (for OCR results)
    - OCR_RESULTS_QUEUE_URL: SQS queue URL for OCR results
    
    Optional:
    - S3_OUTPUT_PREFIX: S3 output prefix (default: "ocr-results/")

Author: Recovery Script Generator
Version: 1.0.0
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from dotenv import load_dotenv


class ForwardScriptConfig:
    """Configuration for the forward script."""
    
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
        self.queue_url = os.getenv("OCR_RESULTS_QUEUE_URL")
        
        # Optional configuration
        self.s3_output_prefix = os.getenv("S3_OUTPUT_PREFIX", "ocr-results/")
        if self.s3_output_prefix and not self.s3_output_prefix.endswith("/"):
            self.s3_output_prefix += "/"
        
        # Validate required configuration
        if not self.s3_input_bucket:
            raise ValueError("S3_INPUT_BUCKET environment variable is required")
        if not self.s3_output_bucket:
            raise ValueError("S3_OUTPUT_BUCKET environment variable is required")
        if not self.queue_url:
            raise ValueError("OCR_RESULTS_QUEUE_URL environment variable is required")
        
        # Detect FIFO queue
        self.is_fifo_queue = self.queue_url.endswith(".fifo")


class S3OCRScanner:
    """Scans S3 bucket for OCR result files."""
    
    def __init__(self, config: ForwardScriptConfig):
        """Initialize the S3 scanner.
        
        Args:
            config: Forward script configuration
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
    
    def scan_ocr_results(
        self,
        prefix: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Scan S3 output bucket for OCR result files (.md).
        
        Args:
            prefix: Optional S3 prefix to filter objects
            limit: Optional maximum number of objects to return
            
        Returns:
            List of S3 object keys (OCR result files)
        """
        # Use provided prefix or default output prefix
        if prefix:
            scan_prefix = prefix
        else:
            scan_prefix = self.config.s3_output_prefix
        
        print(f"Scanning S3 output bucket: s3://{self.config.s3_output_bucket}/{scan_prefix}")
        
        ocr_result_keys = []
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
                    # Check if limit reached
                    if limit and len(ocr_result_keys) >= limit:
                        print(f"Reached limit of {limit} objects")
                        return ocr_result_keys
                    
                    # Filter by .md extension
                    key = obj["Key"]
                    if key.endswith(".md"):
                        ocr_result_keys.append(key)
            
            print(f"Found {len(ocr_result_keys)} OCR result files")
            return ocr_result_keys
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"Error scanning output bucket: {error_code} - {e}")
            raise
    
    def get_ocr_content(self, ocr_key: str) -> str:
        """Download OCR result content from S3.
        
        Args:
            ocr_key: S3 key of the OCR result file
            
        Returns:
            OCR markdown content as string
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.s3_output_bucket,
                Key=ocr_key
            )
            content = response["Body"].read().decode("utf-8")
            return content
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            print(f"Error reading OCR result {ocr_key}: {error_code} - {e}")
            raise
    
    def extract_metadata_from_path(self, ocr_key: str) -> Dict:
        """Extract metadata from OCR result S3 path.
        
        The path structure is: ocr-results/{original-path}/{filename}.md
        We need to extract document_id and page_number from the path.
        
        Args:
            ocr_key: S3 key of the OCR result file
            
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}
        
        # Remove the output prefix to get the relative path
        relative_path = ocr_key
        if ocr_key.startswith(self.config.s3_output_prefix):
            relative_path = ocr_key[len(self.config.s3_output_prefix):]
        
        # Get filename without extension
        path_obj = Path(relative_path)
        filename_base = path_obj.stem
        
        # Try to extract document_id and page_number from path
        # Common patterns:
        # - book-123/page-005.md -> document_id=book-123, page_number=5
        # - documents/2024/record-456/page-010.md -> document_id=record-456, page_number=10
        
        # Get parent directory as potential document_id
        parent_parts = path_obj.parent.parts
        if parent_parts:
            # Use the last directory as document_id
            metadata["document_id"] = parent_parts[-1]
        else:
            # Use filename as document_id if no parent directory
            metadata["document_id"] = filename_base
        
        # Try to extract page number from filename
        # Patterns: page-005, page_005, 005, p005, etc.
        page_match = re.search(r'(?:page[-_]?)?(\d+)', filename_base, re.IGNORECASE)
        if page_match:
            try:
                metadata["page_number"] = int(page_match.group(1))
            except ValueError:
                metadata["page_number"] = None
        else:
            metadata["page_number"] = None
        
        # Store the original filename
        metadata["filename"] = path_obj.name
        
        return metadata
    
    def get_source_image_uri(self, ocr_key: str) -> str:
        """Construct source image URI from OCR result key.
        
        Args:
            ocr_key: S3 key of the OCR result file
            
        Returns:
            S3 URI of the source image
        """
        # Remove output prefix and .md extension
        relative_path = ocr_key
        if ocr_key.startswith(self.config.s3_output_prefix):
            relative_path = ocr_key[len(self.config.s3_output_prefix):]
        
        # Remove .md extension
        image_path = str(Path(relative_path).with_suffix(""))
        
        # Try common image extensions
        # We'll use .jpg as default since we can't know the exact extension
        # The actual extension doesn't matter much for the message
        image_path += ".jpg"
        
        return f"s3://{self.config.s3_input_bucket}/{image_path}"


class MessageConstructor:
    """Constructs SQS messages for OCR results."""
    
    def __init__(self, config: ForwardScriptConfig):
        """Initialize the message constructor.
        
        Args:
            config: Forward script configuration
        """
        self.config = config
    
    def construct_message(
        self,
        ocr_key: str,
        markdown_text: str,
        metadata: Dict,
        source_image_uri: str
    ) -> Dict:
        """Construct SQS message body for an OCR result.
        
        Args:
            ocr_key: S3 key of the OCR result file
            markdown_text: OCR markdown content
            metadata: Extracted metadata
            source_image_uri: S3 URI of the source image
            
        Returns:
            Message body dictionary matching the OCR microservice output format
        """
        # Generate message ID and timestamp
        message_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Construct OCR result URI
        ocr_result_uri = f"s3://{self.config.s3_output_bucket}/{ocr_key}"
        
        # Build message payload (matching SQSPublisher.publish_ocr_result format)
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
        
        # Remove None values from metadata to keep message clean
        message["metadata"] = {
            k: v for k, v in message["metadata"].items() if v is not None
        }
        
        return message


class SQSMessageSender:
    """Sends messages to SQS queue."""
    
    def __init__(self, config: ForwardScriptConfig):
        """Initialize the SQS sender.
        
        Args:
            config: Forward script configuration
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
            doc_id = message_body.get("metadata", {}).get("document_id", "unknown")
            page_num = message_body.get("metadata", {}).get("page_number", "?")
            print(f"[DRY RUN] Would send message for: document_id={doc_id}, page={page_num}")
            return None
        
        # Prepare base send_message parameters
        send_params = {
            "QueueUrl": self.config.queue_url,
            "MessageBody": json.dumps(message_body, ensure_ascii=False),
        }
        
        # Add FIFO-specific parameters if needed
        if self.config.is_fifo_queue:
            # MessageGroupId: Group by document_id
            document_id = message_body.get("metadata", {}).get("document_id", "unknown")
            message_group_id = f"doc-{document_id}"
            
            # MessageDeduplicationId: Use message_id from body
            message_deduplication_id = message_body.get("message_id", str(uuid.uuid4()))
            
            send_params["MessageGroupId"] = message_group_id
            send_params["MessageDeduplicationId"] = message_deduplication_id
        
        try:
            response = self.sqs_client.send_message(**send_params)
            sqs_message_id = response.get("MessageId", "")
            doc_id = message_body.get("metadata", {}).get("document_id", "unknown")
            page_num = message_body.get("metadata", {}).get("page_number", "?")
            print(f"✓ Sent message {sqs_message_id} for: document_id={doc_id}, page={page_num}")
            return sqs_message_id
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            doc_id = message_body.get("metadata", {}).get("document_id", "unknown")
            print(f"✗ Error sending message for document_id={doc_id}: {error_code} - {e}")
            return None


def main():
    """Main entry point for the forward script."""
    parser = argparse.ArgumentParser(
        description="Forward OCR results to the next processing stage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to preview what would be sent
  python forward_ocr_results.py --dry-run

  # Actually send messages
  python forward_ocr_results.py

  # Filter by S3 prefix
  python forward_ocr_results.py --prefix ocr-results/documents/book-123/

  # Limit number of messages
  python forward_ocr_results.py --max-messages 100

  # Custom batch size
  python forward_ocr_results.py --batch-size 5

  # Verbose output with dry run
  python forward_ocr_results.py --dry-run --verbose
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
        help="S3 prefix to filter objects (e.g., 'ocr-results/documents/book-123/')"
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
        help="Maximum number of messages to send (optional limit)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--skip-content",
        action="store_true",
        help="Skip downloading OCR content (faster, but messages won't include markdown_text)"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print("=" * 70)
    print("OCR Image Microservice - Forward OCR Results Script")
    print("=" * 70)
    print()
    
    if args.dry_run:
        print("⚠️  DRY RUN MODE - No messages will be sent")
        print()
    
    try:
        # Load configuration
        print("Loading configuration...")
        config = ForwardScriptConfig()
        print(f"  S3 Input Bucket: {config.s3_input_bucket}")
        print(f"  S3 Output Bucket: {config.s3_output_bucket}")
        print(f"  S3 Output Prefix: {config.s3_output_prefix}")
        print(f"  SQS Queue: {config.queue_url}")
        print(f"  FIFO Queue: {config.is_fifo_queue}")
        print()
        
        # Initialize components
        scanner = S3OCRScanner(config)
        constructor = MessageConstructor(config)
        sender = SQSMessageSender(config)
        
        # Step 1: Scan output bucket for OCR results
        print("Step 1: Scanning output bucket for OCR results...")
        ocr_keys = scanner.scan_ocr_results(
            prefix=args.prefix,
            limit=args.max_messages,
        )
        
        if not ocr_keys:
            print("No OCR results found matching the criteria.")
            return 0
        
        print()
        
        # Step 2: Process and send messages
        print(f"Step 2: Processing {len(ocr_keys)} OCR results...")
        print()
        
        success_count = 0
        error_count = 0
        
        # Process in batches
        for i in range(0, len(ocr_keys), args.batch_size):
            batch = ocr_keys[i:i + args.batch_size]
            
            if args.verbose:
                print(f"Processing batch {i // args.batch_size + 1} ({len(batch)} files)...")
            
            for ocr_key in batch:
                try:
                    # Extract metadata from path
                    metadata = scanner.extract_metadata_from_path(ocr_key)
                    
                    # Get source image URI
                    source_image_uri = scanner.get_source_image_uri(ocr_key)
                    
                    # Get OCR content (unless skipped)
                    if args.skip_content:
                        markdown_text = ""
                    else:
                        markdown_text = scanner.get_ocr_content(ocr_key)
                    
                    # Construct message
                    message_body = constructor.construct_message(
                        ocr_key=ocr_key,
                        markdown_text=markdown_text,
                        metadata=metadata,
                        source_image_uri=source_image_uri
                    )
                    
                    if args.verbose and args.dry_run:
                        print(f"  OCR Key: {ocr_key}")
                        print(f"  Metadata: {metadata}")
                        print(f"  Message: {json.dumps(message_body, indent=2)[:500]}...")
                    
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
                    print(f"✗ Error processing {ocr_key}: {e}")
                    error_count += 1
                    if args.verbose:
                        import traceback
                        traceback.print_exc()
        
        # Print summary
        print()
        print("=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"Total OCR results found: {len(ocr_keys)}")
        print(f"Messages sent successfully: {success_count}")
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
