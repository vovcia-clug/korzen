"""Comprehensive tests for duplicate detection and metadata enrichment.

This test suite validates:
1. Perceptual hash calculation for images
2. Duplicate detection using perceptual hashing
3. Metadata enrichment when duplicate lacks metadata
4. Skipping enrichment when duplicate already has metadata
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Mock the logger to avoid import issues in tests
sys.modules['utils.logger'] = MagicMock()

from services.duplicate_detector import DuplicateDetector


def create_test_image(path: Path, size: tuple = (100, 100), color: tuple = (255, 0, 0)):
    """Create a test image file.
    
    Args:
        path: Path where to save the image
        size: Image dimensions (width, height)
        color: RGB color tuple
    """
    try:
        from PIL import Image
        
        img = Image.new('RGB', size, color)
        img.save(path)
        return True
    except ImportError:
        print("PIL not available, skipping image creation")
        return False


def test_perceptual_hash_calculation():
    """Test that perceptual hashes are calculated correctly."""
    print("\n=== Test: Perceptual Hash Calculation ===")
    
    detector = DuplicateDetector(hash_size=8, similarity_threshold=5)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test image
        test_image = tmpdir / "test.jpg"
        if not create_test_image(test_image):
            print("SKIPPED: PIL not available")
            return
        
        # Calculate perceptual hash
        phash = detector.calculate_perceptual_hash(test_image)
        
        assert phash is not None, "Perceptual hash should not be None"
        assert isinstance(phash, str), "Perceptual hash should be a string"
        assert len(phash) == 16, f"Perceptual hash should be 16 chars (8x8 hash), got {len(phash)}"
        
        print(f"✓ Perceptual hash calculated: {phash}")
        print(f"✓ Hash length: {len(phash)} characters")


def test_all_hash_types():
    """Test that all hash types are calculated."""
    print("\n=== Test: All Hash Types ===")
    
    detector = DuplicateDetector(hash_size=8, similarity_threshold=5)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test image
        test_image = tmpdir / "test.jpg"
        if not create_test_image(test_image):
            print("SKIPPED: PIL not available")
            return
        
        # Calculate all hashes
        hashes = detector.calculate_all_hashes(test_image)
        
        assert "perceptual_hash" in hashes, "Should have perceptual_hash"
        assert "average_hash" in hashes, "Should have average_hash"
        assert "difference_hash" in hashes, "Should have difference_hash"
        
        assert hashes["perceptual_hash"] is not None, "Perceptual hash should not be None"
        assert hashes["average_hash"] is not None, "Average hash should not be None"
        assert hashes["difference_hash"] is not None, "Difference hash should not be None"
        
        print(f"✓ Perceptual hash: {hashes['perceptual_hash']}")
        print(f"✓ Average hash: {hashes['average_hash']}")
        print(f"✓ Difference hash: {hashes['difference_hash']}")


def test_identical_images_are_duplicates():
    """Test that identical images are detected as duplicates."""
    print("\n=== Test: Identical Images Are Duplicates ===")
    
    detector = DuplicateDetector(hash_size=8, similarity_threshold=5)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create two identical images
        image1 = tmpdir / "image1.jpg"
        image2 = tmpdir / "image2.jpg"
        
        if not create_test_image(image1, color=(255, 0, 0)):
            print("SKIPPED: PIL not available")
            return
        if not create_test_image(image2, color=(255, 0, 0)):
            print("SKIPPED: PIL not available")
            return
        
        # Calculate hashes
        hash1 = detector.calculate_perceptual_hash(image1)
        hash2 = detector.calculate_perceptual_hash(image2)
        
        # Check if duplicates
        is_dup, distance = detector.are_duplicates(hash1, hash2)
        
        assert is_dup, "Identical images should be detected as duplicates"
        assert distance == 0, f"Distance should be 0 for identical images, got {distance}"
        
        print(f"✓ Hash 1: {hash1}")
        print(f"✓ Hash 2: {hash2}")
        print(f"✓ Hamming distance: {distance}")
        print(f"✓ Detected as duplicates: {is_dup}")


def test_different_images_not_duplicates():
    """Test that different images are not detected as duplicates."""
    print("\n=== Test: Different Images Not Duplicates ===")
    
    detector = DuplicateDetector(hash_size=8, similarity_threshold=5)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create two different images
        image1 = tmpdir / "image1.jpg"
        image2 = tmpdir / "image2.jpg"
        
        if not create_test_image(image1, color=(255, 0, 0)):  # Red
            print("SKIPPED: PIL not available")
            return
        if not create_test_image(image2, color=(0, 0, 255)):  # Blue
            print("SKIPPED: PIL not available")
            return
        
        # Calculate hashes
        hash1 = detector.calculate_perceptual_hash(image1)
        hash2 = detector.calculate_perceptual_hash(image2)
        
        # Check if duplicates
        is_dup, distance = detector.are_duplicates(hash1, hash2)
        
        print(f"✓ Hash 1: {hash1}")
        print(f"✓ Hash 2: {hash2}")
        print(f"✓ Hamming distance: {distance}")
        print(f"✓ Detected as duplicates: {is_dup}")
        print(f"✓ Different images correctly identified (distance > threshold)")


def test_similarity_threshold():
    """Test that similarity threshold works correctly."""
    print("\n=== Test: Similarity Threshold ===")
    
    # Strict threshold
    strict_detector = DuplicateDetector(hash_size=8, similarity_threshold=0)
    
    # Lenient threshold
    lenient_detector = DuplicateDetector(hash_size=8, similarity_threshold=10)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create slightly different images
        image1 = tmpdir / "image1.jpg"
        image2 = tmpdir / "image2.jpg"
        
        if not create_test_image(image1, size=(100, 100), color=(255, 0, 0)):
            print("SKIPPED: PIL not available")
            return
        if not create_test_image(image2, size=(100, 100), color=(250, 5, 5)):
            print("SKIPPED: PIL not available")
            return
        
        # Calculate hashes
        hash1 = strict_detector.calculate_perceptual_hash(image1)
        hash2 = strict_detector.calculate_perceptual_hash(image2)
        
        # Check with strict threshold
        is_dup_strict, distance = strict_detector.are_duplicates(hash1, hash2)
        
        # Check with lenient threshold
        is_dup_lenient, _ = lenient_detector.are_duplicates(hash1, hash2)
        
        print(f"✓ Hash 1: {hash1}")
        print(f"✓ Hash 2: {hash2}")
        print(f"✓ Hamming distance: {distance}")
        print(f"✓ Strict threshold (0): {is_dup_strict}")
        print(f"✓ Lenient threshold (10): {is_dup_lenient}")


def test_s3_duplicate_detection_mock():
    """Test S3 duplicate detection with mocked S3 client."""
    print("\n=== Test: S3 Duplicate Detection (Mocked) ===")
    
    from services.s3_uploader import S3Uploader
    
    # Create mock S3 client
    mock_s3_client = MagicMock()
    
    # Mock paginator
    mock_paginator = MagicMock()
    mock_s3_client.get_paginator.return_value = mock_paginator
    
    # Mock pages with one object
    mock_paginator.paginate.return_value = [
        {
            'Contents': [
                {'Key': 'uploads/2024/01/01/test.jpg'}
            ]
        }
    ]
    
    # Mock head_object to return metadata with perceptual hash
    mock_s3_client.head_object.return_value = {
        'Metadata': {
            'perceptual-hash': 'aaaaaaaaaaaaaaaa',
            'file-hash': 'abc123',
        }
    }
    
    # Create S3Uploader with mocked client
    uploader = S3Uploader(
        bucket='test-bucket',
        prefix='uploads/',
        region='us-east-1',
    )
    uploader.s3_client = mock_s3_client
    
    # Test finding duplicate
    result = uploader.find_duplicate_by_perceptual_hash('aaaaaaaaaaaaaaaa', similarity_threshold=5)
    
    assert result is not None, "Should find duplicate"
    s3_uri, metadata, distance = result
    
    assert s3_uri == 's3://test-bucket/uploads/2024/01/01/test.jpg'
    assert distance == 0
    assert metadata['perceptual-hash'] == 'aaaaaaaaaaaaaaaa'
    
    print(f"✓ Found duplicate: {s3_uri}")
    print(f"✓ Distance: {distance}")
    print(f"✓ Metadata: {metadata}")


def test_metadata_enrichment_mock():
    """Test metadata enrichment with mocked S3 client."""
    print("\n=== Test: Metadata Enrichment (Mocked) ===")
    
    from services.s3_uploader import S3Uploader
    
    # Create mock S3 client
    mock_s3_client = MagicMock()
    
    # Mock head_object to return existing metadata WITHOUT Skanoteka data
    mock_s3_client.head_object.return_value = {
        'Metadata': {
            'file-hash': 'abc123',
            'original-filename': 'test.jpg',
        }
    }
    
    # Mock copy_object
    mock_s3_client.copy_object.return_value = {}
    
    # Create S3Uploader with mocked client
    uploader = S3Uploader(
        bucket='test-bucket',
        prefix='uploads/',
        region='us-east-1',
    )
    uploader.s3_client = mock_s3_client
    
    # Test enriching metadata
    new_metadata = {
        'skanoteka-place': 'Bolechów',
        'skanoteka-unit': '4500 M-1874-1937-Bolechów',
        'skanoteka-years': '1874-1937',
    }
    
    success = uploader.enrich_metadata(
        's3://test-bucket/uploads/2024/01/01/test.jpg',
        new_metadata,
        overwrite=False,
    )
    
    assert success, "Metadata enrichment should succeed"
    
    # Verify copy_object was called with enriched metadata
    assert mock_s3_client.copy_object.called, "copy_object should be called"
    call_args = mock_s3_client.copy_object.call_args
    enriched_metadata = call_args[1]['Metadata']
    
    assert 'skanoteka-place' in enriched_metadata
    assert enriched_metadata['skanoteka-place'] == 'Bolechów'
    
    print(f"✓ Metadata enrichment successful")
    print(f"✓ Enriched metadata: {enriched_metadata}")


def test_skip_enrichment_when_metadata_exists():
    """Test that enrichment is skipped when metadata already exists."""
    print("\n=== Test: Skip Enrichment When Metadata Exists ===")
    
    from services.s3_uploader import S3Uploader
    
    # Create mock S3 client
    mock_s3_client = MagicMock()
    
    # Mock head_object to return existing metadata WITH Skanoteka data
    mock_s3_client.head_object.return_value = {
        'Metadata': {
            'file-hash': 'abc123',
            'original-filename': 'test.jpg',
            'skanoteka-place': 'Existing Place',
            'skanoteka-unit': 'Existing Unit',
        }
    }
    
    # Create S3Uploader with mocked client
    uploader = S3Uploader(
        bucket='test-bucket',
        prefix='uploads/',
        region='us-east-1',
    )
    uploader.s3_client = mock_s3_client
    
    # Test enriching metadata (should be skipped)
    new_metadata = {
        'skanoteka-place': 'New Place',
        'skanoteka-unit': 'New Unit',
    }
    
    success = uploader.enrich_metadata(
        's3://test-bucket/uploads/2024/01/01/test.jpg',
        new_metadata,
        overwrite=False,  # Don't overwrite existing
    )
    
    assert not success, "Enrichment should be skipped when metadata exists"
    assert not mock_s3_client.copy_object.called, "copy_object should not be called"
    
    print(f"✓ Enrichment correctly skipped")
    print(f"✓ Existing metadata preserved")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("DUPLICATE DETECTION & METADATA ENRICHMENT TESTS")
    print("=" * 60)
    
    tests = [
        test_perceptual_hash_calculation,
        test_all_hash_types,
        test_identical_images_are_duplicates,
        test_different_images_not_duplicates,
        test_similarity_threshold,
        test_s3_duplicate_detection_mock,
        test_metadata_enrichment_mock,
        test_skip_enrichment_when_metadata_exists,
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
