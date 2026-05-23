"""Standalone test for S3 URI parsing logic (no dependencies)."""
import re
from urllib.parse import urlparse


def parse_s3_uri(s3_uri: str) -> tuple:
    """
    Parse S3 URI into bucket and key components.
    
    Supports both formats:
    - S3 URI: s3://bucket/key
    - HTTPS URL: https://bucket.s3.region.amazonaws.com/key
    - HTTPS URL (path-style): https://s3.region.amazonaws.com/bucket/key
    """
    print(f"Parsing: {s3_uri}")
    
    # Handle s3:// format
    if s3_uri.startswith("s3://"):
        print("  Format: s3://")
        path = s3_uri[5:]
        parts = path.split("/", 1)
        
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URI format: {s3_uri}")
        
        bucket, key = parts
        print(f"  Result: bucket={bucket}, key={key}")
        return bucket, key
    
    # Handle https:// format
    elif s3_uri.startswith("https://"):
        print("  Format: https://")
        parsed = urlparse(s3_uri)
        hostname = parsed.hostname
        path = parsed.path.lstrip('/')
        
        if not hostname or not path:
            raise ValueError(f"Invalid HTTPS S3 URL format: {s3_uri}")
        
        # Virtual-hosted-style URL
        virtual_hosted_match = re.match(
            r'^(.+?)\.s3[.-]([a-z0-9-]+)?\.amazonaws\.com$',
            hostname
        )
        
        if virtual_hosted_match:
            bucket = virtual_hosted_match.group(1)
            key = path
            print(f"  Style: Virtual-hosted")
            print(f"  Result: bucket={bucket}, key={key}")
            return bucket, key
        
        # Path-style URL
        path_style_match = re.match(
            r'^s3[.-]([a-z0-9-]+)?\.amazonaws\.com$',
            hostname
        )
        
        if path_style_match:
            path_parts = path.split('/', 1)
            if len(path_parts) != 2:
                raise ValueError(f"Invalid path-style S3 URL format: {s3_uri}")
            bucket, key = path_parts
            print(f"  Style: Path-style")
            print(f"  Result: bucket={bucket}, key={key}")
            return bucket, key
        
        raise ValueError(f"Invalid S3 HTTPS URL format: {s3_uri}")
    
    else:
        raise ValueError(f"Invalid S3 URI format: {s3_uri}")


# Test cases
print("="*70)
print("TESTING S3 URI PARSING")
print("="*70)

test_cases = [
    ("Your actual URL", "https://korzen-images-637992521083-eu-north-1-an.s3.eu-north-1.amazonaws.com/001.jpg"),
    ("S3 URI", "s3://my-bucket/path/to/file.jpg"),
    ("HTTPS virtual-hosted", "https://my-bucket.s3.us-east-1.amazonaws.com/path/to/file.jpg"),
    ("HTTPS path-style", "https://s3.us-east-1.amazonaws.com/my-bucket/file.jpg"),
]

passed = 0
failed = 0

for name, uri in test_cases:
    print(f"\nTest: {name}")
    try:
        bucket, key = parse_s3_uri(uri)
        print(f"  ✓ SUCCESS")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1

print("\n" + "="*70)
print(f"Results: {passed} passed, {failed} failed")
print("="*70)
