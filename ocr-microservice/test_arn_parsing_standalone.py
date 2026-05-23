#!/usr/bin/env python3
"""Standalone test script to validate ARN parsing for S3 URIs."""

import re
from urllib.parse import urlparse

def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """
    Parse S3 URI into bucket and key components.
    
    Supports multiple formats:
    - S3 URI: s3://bucket/key
    - S3 ARN: arn:aws:s3:::bucket/key or arn:aws:s3:region:account:accesspoint/...
    - HTTPS URL: https://bucket.s3.region.amazonaws.com/key
    - HTTPS URL (path-style): https://s3.region.amazonaws.com/bucket/key
    
    Args:
        s3_uri: S3 URI, ARN, or HTTPS URL
    
    Returns:
        Tuple of (bucket, key)
    
    Raises:
        ValueError: If URI format is invalid
    """
    print(f"→ Parsing: {s3_uri}")
    
    # Handle S3 ARN format: arn:aws:s3:::bucket-name/key or arn:aws:s3:::bucket-name
    if s3_uri.startswith("arn:aws:s3"):
        print("  Format: ARN")
        
        # Parse the ARN
        # Standard S3 ARN for objects: arn:aws:s3:::bucket-name/key-name
        # Note: S3 object ARNs have three colons after s3 (no region/account)
        arn_match = re.match(r'^arn:aws:s3:::(.+?)(?:/(.+))?$', s3_uri)
        
        if arn_match:
            bucket = arn_match.group(1)
            key = arn_match.group(2)
            
            if not key:
                raise ValueError(f"S3 ARN missing object key: {s3_uri}")
            
            print(f"  Bucket: {bucket}")
            print(f"  Key: {key}")
            return bucket, key
        else:
            raise ValueError(
                f"Unsupported S3 ARN format. Expected 'arn:aws:s3:::bucket/key' but got: {s3_uri}"
            )
    
    # Handle s3:// format
    elif s3_uri.startswith("s3://"):
        print("  Format: s3://")
        # Remove s3:// prefix and split
        path = s3_uri[5:]
        parts = path.split("/", 1)
        
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        bucket, key = parts
        print(f"  Bucket: {bucket}")
        print(f"  Key: {key}")
        return bucket, key
    
    # Handle https:// format
    elif s3_uri.startswith("https://"):
        print("  Format: https://")
        parsed = urlparse(s3_uri)
        hostname = parsed.hostname
        path = parsed.path.lstrip('/')
        
        if not hostname or not path:
            raise ValueError(f"Invalid HTTPS S3 URL format: {s3_uri}")
        
        # Virtual-hosted-style URL: https://bucket.s3.region.amazonaws.com/key
        virtual_hosted_match = re.match(
            r'^(.+?)\.s3[.-]([a-z0-9-]+)?\.amazonaws\.com$',
            hostname
        )
        
        if virtual_hosted_match:
            bucket = virtual_hosted_match.group(1)
            key = path
            print(f"  Bucket: {bucket}")
            print(f"  Key: {key}")
            return bucket, key
        
        # Path-style URL: https://s3.region.amazonaws.com/bucket/key
        path_style_match = re.match(
            r'^s3[.-]([a-z0-9-]+)?\.amazonaws\.com$',
            hostname
        )
        
        if path_style_match:
            path_parts = path.split('/', 1)
            if len(path_parts) != 2:
                raise ValueError(f"Invalid path-style S3 URL format: {s3_uri}")
            bucket, key = path_parts
            print(f"  Bucket: {bucket}")
            print(f"  Key: {key}")
            return bucket, key
        
        raise ValueError(
            f"Invalid S3 HTTPS URL format (unknown hostname pattern): {s3_uri}"
        )
    
    else:
        raise ValueError(
            f"Invalid S3 URI format. Must start with 's3://', 'arn:aws:s3', or 'https://': {s3_uri}"
        )


def test_arn_parsing():
    """Test ARN parsing with the problematic ARN from the error."""
    
    # Test cases from the error message and various formats
    test_cases = [
        # The problematic ARN from your error (missing key - should fail)
        ("arn:aws:s3:::korzen-images-637992521083-eu-north-1-an", False),
        
        # Complete ARN with object key (should succeed)
        ("arn:aws:s3:::korzen-images-637992521083-eu-north-1-an/test-image.jpg", True),
        
        # Standard s3:// URI (should succeed)
        ("s3://korzen-images-637992521083-eu-north-1-an/test-image.jpg", True),
        
        # HTTPS URL formats (should succeed)
        ("https://korzen-images-637992521083-eu-north-1-an.s3.eu-north-1.amazonaws.com/test-image.jpg", True),
        ("https://s3.eu-north-1.amazonaws.com/korzen-images-637992521083-eu-north-1-an/test-image.jpg", True)
    ]
    
    print("\n" + "="*80)
    print("Testing S3 URI/ARN Parsing")
    print("="*80 + "\n")
    
    passed = 0
    failed = 0
    
    for i, (test_uri, should_succeed) in enumerate(test_cases, 1):
        print(f"\nTest #{i}: {'(Expected to succeed)' if should_succeed else '(Expected to fail)'}")
        print("-" * 80)
        
        try:
            bucket, key = parse_s3_uri(test_uri)
            if should_succeed:
                print(f"✓ SUCCESS - Correctly parsed")
                passed += 1
            else:
                print(f"✗ FAILED - Should have raised ValueError")
                failed += 1
        except ValueError as e:
            if not should_succeed:
                print(f"✓ SUCCESS - Correctly rejected with error: {e}")
                passed += 1
            else:
                print(f"✗ FAILED - Should have succeeded but got error: {e}")
                failed += 1
        except Exception as e:
            print(f"✗ UNEXPECTED ERROR: {type(e).__name__}: {e}")
            failed += 1
        
        print()
    
    print("="*80)
    print(f"Testing Complete: {passed} passed, {failed} failed")
    print("="*80 + "\n")


if __name__ == "__main__":
    test_arn_parsing()
