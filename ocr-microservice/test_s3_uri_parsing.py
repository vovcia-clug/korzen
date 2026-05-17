"""Test S3 URI parsing with different formats."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.s3_handler import S3Handler
from utils.logger import get_logger

logger = get_logger(__name__)


def test_parse_s3_uri():
    """Test parsing various S3 URI formats."""
    
    # Initialize S3Handler (config not important for this test)
    handler = S3Handler(
        aws_config={"region_name": "eu-north-1"},
        input_bucket="test-bucket",
        output_bucket="test-output"
    )
    
    # Test cases
    test_cases = [
        {
            "name": "S3 URI format",
            "uri": "s3://my-bucket/path/to/file.jpg",
            "expected_bucket": "my-bucket",
            "expected_key": "path/to/file.jpg"
        },
        {
            "name": "HTTPS virtual-hosted-style (with region)",
            "uri": "https://korzen-images-637992521083-eu-north-1-an.s3.eu-north-1.amazonaws.com/001.jpg",
            "expected_bucket": "korzen-images-637992521083-eu-north-1-an",
            "expected_key": "001.jpg"
        },
        {
            "name": "HTTPS virtual-hosted-style (with dots)",
            "uri": "https://my-bucket.s3.us-east-1.amazonaws.com/path/to/file.jpg",
            "expected_bucket": "my-bucket",
            "expected_key": "path/to/file.jpg"
        },
        {
            "name": "HTTPS virtual-hosted-style (no region)",
            "uri": "https://my-bucket.s3.amazonaws.com/file.jpg",
            "expected_bucket": "my-bucket",
            "expected_key": "file.jpg"
        },
        {
            "name": "HTTPS path-style",
            "uri": "https://s3.us-east-1.amazonaws.com/my-bucket/path/to/file.jpg",
            "expected_bucket": "my-bucket",
            "expected_key": "path/to/file.jpg"
        },
        {
            "name": "HTTPS path-style (no region)",
            "uri": "https://s3.amazonaws.com/my-bucket/file.jpg",
            "expected_bucket": "my-bucket",
            "expected_key": "file.jpg"
        }
    ]
    
    # Run tests
    passed = 0
    failed = 0
    
    for test in test_cases:
        try:
            bucket, key = handler.parse_s3_uri(test["uri"])
            
            if bucket == test["expected_bucket"] and key == test["expected_key"]:
                logger.info(f"✓ PASSED: {test['name']}")
                logger.info(f"  URI: {test['uri']}")
                logger.info(f"  Parsed: bucket={bucket}, key={key}")
                passed += 1
            else:
                logger.error(f"✗ FAILED: {test['name']}")
                logger.error(f"  URI: {test['uri']}")
                logger.error(f"  Expected: bucket={test['expected_bucket']}, key={test['expected_key']}")
                logger.error(f"  Got: bucket={bucket}, key={key}")
                failed += 1
                
        except Exception as e:
            logger.error(f"✗ FAILED: {test['name']}")
            logger.error(f"  URI: {test['uri']}")
            logger.error(f"  Exception: {e}")
            failed += 1
    
    # Test invalid formats
    invalid_cases = [
        "ftp://bucket/key",
        "https://example.com/file.jpg",
        "s3://bucket-only",
        "not-a-uri",
        ""
    ]
    
    logger.info("\n--- Testing invalid formats (should raise ValueError) ---")
    
    for invalid_uri in invalid_cases:
        try:
            handler.parse_s3_uri(invalid_uri)
            logger.error(f"✗ FAILED: Should have raised ValueError for: {invalid_uri}")
            failed += 1
        except ValueError as e:
            logger.info(f"✓ PASSED: Correctly rejected invalid URI: {invalid_uri}")
            logger.info(f"  Error: {e}")
            passed += 1
        except Exception as e:
            logger.error(f"✗ FAILED: Wrong exception type for: {invalid_uri}")
            logger.error(f"  Exception: {e}")
            failed += 1
    
    # Summary
    total = passed + failed
    logger.info(f"\n{'='*60}")
    logger.info(f"Test Results: {passed}/{total} passed, {failed}/{total} failed")
    logger.info(f"{'='*60}")
    
    return failed == 0


if __name__ == "__main__":
    success = test_parse_s3_uri()
    sys.exit(0 if success else 1)
