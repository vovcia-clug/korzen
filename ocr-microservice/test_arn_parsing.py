#!/usr/bin/env python3
"""Test script to validate ARN parsing for S3 URIs."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.s3_handler import S3Handler
from utils.logger import get_logger

logger = get_logger(__name__)

def test_arn_parsing():
    """Test ARN parsing with the problematic ARN from the error."""
    
    # Create a minimal S3Handler instance (won't use actual AWS operations)
    handler = S3Handler(
        aws_config={
            'region_name': 'eu-north-1',
            'aws_access_key_id': 'test',
            'aws_secret_access_key': 'test'
        },
        input_bucket='test-bucket',
        output_bucket='test-bucket'
    )
    
    # Test cases from the error message and various formats
    test_cases = [
        # The problematic ARN from your error
        "arn:aws:s3:::korzen-images-637992521083-eu-north-1-an",
        
        # Complete ARN with object key
        "arn:aws:s3:::korzen-images-637992521083-eu-north-1-an/test-image.jpg",
        
        # Standard s3:// URI
        "s3://korzen-images-637992521083-eu-north-1-an/test-image.jpg",
        
        # HTTPS URL formats
        "https://korzen-images-637992521083-eu-north-1-an.s3.eu-north-1.amazonaws.com/test-image.jpg",
        "https://s3.eu-north-1.amazonaws.com/korzen-images-637992521083-eu-north-1-an/test-image.jpg"
    ]
    
    print("\n" + "="*80)
    print("Testing S3 URI/ARN Parsing")
    print("="*80 + "\n")
    
    for i, test_uri in enumerate(test_cases, 1):
        print(f"\nTest #{i}:")
        print(f"Input:  {test_uri}")
        print("-" * 80)
        
        try:
            bucket, key = handler.parse_s3_uri(test_uri)
            print(f"✓ SUCCESS")
            print(f"  Bucket: {bucket}")
            print(f"  Key:    {key}")
        except ValueError as e:
            print(f"✗ FAILED")
            print(f"  Error: {e}")
        except Exception as e:
            print(f"✗ UNEXPECTED ERROR")
            print(f"  Error: {type(e).__name__}: {e}")
    
    print("\n" + "="*80)
    print("Testing Complete")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_arn_parsing()
