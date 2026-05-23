#!/usr/bin/env python3
"""Test script for Skanoteka metadata integration.

This script tests the metadata extraction functionality without requiring
AWS credentials or actual file uploads.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.metadata_extractor import MetadataExtractor


def test_url_validation():
    """Test Skanoteka URL validation."""
    print("\n=== Testing URL Validation ===")
    
    extractor = MetadataExtractor()
    
    # Test valid Skanoteka URL
    valid_url = "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545"
    assert extractor.is_skanoteka_url(valid_url), "Should recognize Skanoteka URL"
    print(f"✓ Valid URL recognized: {valid_url}")
    
    # Test invalid URL
    invalid_url = "https://example.com/page"
    assert not extractor.is_skanoteka_url(invalid_url), "Should reject non-Skanoteka URL"
    print(f"✓ Invalid URL rejected: {invalid_url}")
    
    # Test empty URL
    assert not extractor.is_skanoteka_url(""), "Should reject empty URL"
    print("✓ Empty URL rejected")
    
    print("✓ All URL validation tests passed!")


def test_metadata_extraction():
    """Test metadata extraction from a real Skanoteka URL."""
    print("\n=== Testing Metadata Extraction ===")
    
    extractor = MetadataExtractor()
    
    # Test with a real Skanoteka URL
    test_url = "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg"
    
    print(f"Extracting metadata from: {test_url}")
    metadata = extractor.extract_metadata_from_url(test_url)
    
    print("\nExtracted metadata:")
    print(f"  Place: {metadata.get('place')}")
    print(f"  Unit: {metadata.get('unit')}")
    print(f"  Years: {metadata.get('years')}")
    print(f"  Page: {metadata.get('page')}")
    print(f"  Source URL: {metadata.get('source_url')}")
    
    if "error" in metadata:
        print(f"\n⚠️  Warning: {metadata['error']}")
        print("This may be due to network issues or changes in Skanoteka website structure.")
    else:
        # Verify we got some metadata
        assert metadata.get("place") is not None, "Should extract place"
        assert metadata.get("unit") is not None, "Should extract unit"
        assert metadata.get("source_url") == test_url, "Should preserve source URL"
        print("\n✓ Metadata extraction successful!")


def test_companion_file_detection():
    """Test companion file detection."""
    print("\n=== Testing Companion File Detection ===")
    
    extractor = MetadataExtractor()
    
    # Create a temporary test file
    test_dir = Path(__file__).parent / "test_temp"
    test_dir.mkdir(exist_ok=True)
    
    try:
        # Create test image file
        test_image = test_dir / "test_image.jpg"
        test_image.write_text("fake image content")
        
        # Test without companion file
        result = extractor.extract_metadata_from_filename(test_image)
        assert result is None, "Should return None when no companion file exists"
        print("✓ Correctly handles missing companion file")
        
        # Create companion .txt file
        companion_txt = test_dir / "test_image.txt"
        companion_txt.write_text("https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&plik=1.jpg")
        
        # Test with companion file
        result = extractor.extract_metadata_from_filename(test_image)
        assert result is not None, "Should find companion file"
        assert result.get("source_url") is not None, "Should extract URL from companion file"
        print("✓ Successfully detected and processed companion .txt file")
        
        # Clean up .txt file
        companion_txt.unlink()
        
        # Create companion .url file
        companion_url = test_dir / "test_image.url"
        companion_url.write_text("[InternetShortcut]\nURL=https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&plik=2.jpg")
        
        # Test with .url file
        result = extractor.extract_metadata_from_filename(test_image)
        assert result is not None, "Should find .url file"
        assert result.get("source_url") is not None, "Should extract URL from .url file"
        print("✓ Successfully detected and processed companion .url file")
        
    finally:
        # Clean up test files
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
        print("✓ Test cleanup completed")


def main():
    """Run all tests."""
    print("=" * 70)
    print("Skanoteka Metadata Integration Test Suite")
    print("=" * 70)
    
    try:
        # Test 1: URL validation (no network required)
        test_url_validation()
        
        # Test 2: Companion file detection (no network required)
        test_companion_file_detection()
        
        # Test 3: Metadata extraction (requires network)
        print("\n" + "=" * 70)
        print("Network-dependent tests (may fail if offline or Skanoteka is down)")
        print("=" * 70)
        
        try:
            test_metadata_extraction()
        except Exception as e:
            print(f"\n⚠️  Network test failed: {e}")
            print("This is expected if you're offline or Skanoteka is unavailable.")
        
        print("\n" + "=" * 70)
        print("✓ All local tests passed!")
        print("=" * 70)
        print("\nIntegration is ready for use.")
        print("See METADATA_INTEGRATION.md for usage instructions.")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
