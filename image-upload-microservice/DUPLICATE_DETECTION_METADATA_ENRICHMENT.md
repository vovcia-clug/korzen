# Duplicate Detection & Metadata Enrichment

This document describes the duplicate detection and metadata enrichment features added to the image-upload-microservice.

## Overview

The service now includes:

1. **Perceptual Hash-Based Duplicate Detection**: Uses image hashing algorithms to detect visually similar images, even if they've been resized, compressed, or slightly modified
2. **Metadata Enrichment**: Automatically enriches existing duplicate images with Skanoteka metadata from new uploads when the existing duplicate lacks metadata
3. **Configurable Behavior**: All features can be enabled/disabled via environment variables

## Features

### 1. Perceptual Image Hashing

The service calculates three types of image hashes for each uploaded image:

- **Perceptual Hash (pHash)**: Robust to minor modifications, resizing, and compression
- **Average Hash (aHash)**: Faster but less robust
- **Difference Hash (dHash)**: Good for detecting crops and edits

These hashes are stored as S3 object metadata and used for duplicate detection.

#### How It Works

1. When an image is uploaded, the service calculates its perceptual hash
2. The hash is compared against existing images in S3
3. If a match is found within the similarity threshold, the image is marked as a duplicate
4. The Hamming distance between hashes determines similarity (lower = more similar)

### 2. Duplicate Detection

The service checks for duplicates in two ways:

1. **File Hash (SHA256)**: Exact byte-for-byte duplicates
2. **Perceptual Hash**: Visually similar images

When a duplicate is detected:
- The upload is skipped (no new S3 object created)
- The original file is handled according to the post-upload action (keep/archive/delete)
- Statistics are updated to track duplicates found

### 3. Metadata Enrichment

When a duplicate is found, the service checks if:
1. The new upload has Skanoteka metadata (from companion .txt or .url files)
2. The existing duplicate in S3 lacks Skanoteka metadata

If both conditions are true, the service enriches the existing duplicate's S3 metadata with the new Skanoteka information.

#### Enrichment Rules

- **Only adds missing metadata**: Existing metadata is never overwritten (unless `overwrite=True`)
- **Skanoteka metadata only**: Only enriches with place, unit, years, page, and source_url
- **Logged operations**: All enrichment operations are logged for audit purposes

## Configuration

### Environment Variables

```bash
# Enable/disable duplicate detection (default: true)
ENABLE_DUPLICATE_DETECTION=true

# Enable/disable metadata extraction from Skanoteka URLs (default: true)
ENABLE_METADATA_EXTRACTION=true

# Enable/disable metadata enrichment for duplicates (default: true)
ENABLE_METADATA_ENRICHMENT=true

# Perceptual hash size - larger = more precise but slower (default: 8)
# 8 = 64-bit hash, 16 = 256-bit hash
PERCEPTUAL_HASH_SIZE=8

# Similarity threshold for duplicate detection (default: 5)
# Range: 0-64 (for hash_size=8)
# 0 = exact match only
# 5 = very similar (recommended)
# 10 = somewhat similar
# 20+ = loosely similar
SIMILARITY_THRESHOLD=5
```

### Recommended Settings

#### Strict Duplicate Detection
```bash
ENABLE_DUPLICATE_DETECTION=true
PERCEPTUAL_HASH_SIZE=8
SIMILARITY_THRESHOLD=0  # Only exact visual matches
```

#### Balanced (Recommended)
```bash
ENABLE_DUPLICATE_DETECTION=true
PERCEPTUAL_HASH_SIZE=8
SIMILARITY_THRESHOLD=5  # Near-exact matches
```

#### Lenient
```bash
ENABLE_DUPLICATE_DETECTION=true
PERCEPTUAL_HASH_SIZE=8
SIMILARITY_THRESHOLD=10  # Similar images
```

## S3 Metadata Schema

The service stores the following metadata on S3 objects:

### Standard Metadata
```
original-filename: <filename>
upload-timestamp: <ISO 8601 timestamp>
upload-service: image-upload-microservice
upload-version: 1.0.0
file-size: <bytes>
file-hash: <SHA256 hash>
hash-algorithm: sha256
image-width: <pixels>
image-height: <pixels>
image-format: <jpeg|png|etc>
```

### Perceptual Hash Metadata
```
perceptual-hash: <16-char hex string>
average-hash: <16-char hex string>
difference-hash: <16-char hex string>
```

### Skanoteka Metadata (if available)
```
skanoteka-place: <place name>
skanoteka-unit: <unit identifier>
skanoteka-years: <year range>
skanoteka-page: <page info>
skanoteka-source-url: <original URL>
```

## Workflow

### Normal Upload (No Duplicate)

```
1. Image detected in watch directory
2. Image validated (format, size, etc.)
3. Skanoteka metadata extracted (if companion file exists)
4. Perceptual hashes calculated
5. S3 checked for duplicates
   → No duplicate found
6. Image uploaded to S3 with all metadata
7. SQS notification sent
8. Post-upload action executed
```

### Duplicate Found (With Metadata Enrichment)

```
1. Image detected in watch directory
2. Image validated (format, size, etc.)
3. Skanoteka metadata extracted (if companion file exists)
4. Perceptual hashes calculated
5. S3 checked for duplicates
   → Duplicate found!
6. Check if duplicate has Skanoteka metadata
   → No metadata found
7. Enrich duplicate with new Skanoteka metadata
8. Skip upload (duplicate already exists)
9. Post-upload action executed on original file
```

### Duplicate Found (No Enrichment Needed)

```
1. Image detected in watch directory
2. Image validated (format, size, etc.)
3. Skanoteka metadata extracted (if companion file exists)
4. Perceptual hashes calculated
5. S3 checked for duplicates
   → Duplicate found!
6. Check if duplicate has Skanoteka metadata
   → Metadata already exists
7. Skip enrichment (don't overwrite)
8. Skip upload (duplicate already exists)
9. Post-upload action executed on original file
```

## Statistics

The service tracks the following statistics:

```python
{
    "files_processed": 100,
    "files_uploaded": 85,
    "files_failed": 2,
    "validation_failures": 1,
    "upload_failures": 0,
    "notification_failures": 0,
    "metadata_extracted": 60,
    "duplicates_found": 13,      # NEW
    "duplicates_enriched": 8,    # NEW
    "success_rate": 0.85
}
```

## API Reference

### DuplicateDetector

```python
from services.duplicate_detector import DuplicateDetector

detector = DuplicateDetector(
    hash_size=8,              # Hash size (4-16)
    similarity_threshold=5,   # Max Hamming distance
)

# Calculate perceptual hash
phash = detector.calculate_perceptual_hash(file_path)

# Calculate all hash types
hashes = detector.calculate_all_hashes(file_path)
# Returns: {
#     "perceptual_hash": "...",
#     "average_hash": "...",
#     "difference_hash": "..."
# }

# Check if two hashes are duplicates
is_dup, distance = detector.are_duplicates(hash1, hash2)
```

### S3Uploader (Enhanced)

```python
from services.s3_uploader import S3Uploader

uploader = S3Uploader(bucket="my-bucket", ...)

# Find duplicate by perceptual hash
result = uploader.find_duplicate_by_perceptual_hash(
    perceptual_hash="abc123...",
    similarity_threshold=5,
)
if result:
    s3_uri, metadata, distance = result
    print(f"Found duplicate: {s3_uri} (distance: {distance})")

# Enrich metadata
success = uploader.enrich_metadata(
    s3_uri="s3://bucket/key",
    new_metadata={
        "skanoteka-place": "Bolechów",
        "skanoteka-unit": "4500 M-1874-1937-Bolechów",
    },
    overwrite=False,  # Don't overwrite existing
)
```

### UploadOrchestrator (Enhanced)

```python
from services.upload_orchestrator import UploadOrchestrator

orchestrator = UploadOrchestrator(
    image_detector=detector,
    s3_uploader=uploader,
    sqs_notifier=notifier,
    enable_duplicate_detection=True,
    enable_metadata_enrichment=True,
    perceptual_hash_size=8,
    similarity_threshold=5,
)

# Process file (handles duplicates automatically)
success = orchestrator.process_file(file_path)

# Get statistics
stats = orchestrator.get_statistics()
print(f"Duplicates found: {stats['duplicates_found']}")
print(f"Duplicates enriched: {stats['duplicates_enriched']}")
```

## Testing

Run the comprehensive test suite:

```bash
cd image-upload-microservice
python test_duplicate_detection.py
```

### Test Coverage

The test suite includes:

1. **Perceptual hash calculation**: Verifies hashes are calculated correctly
2. **All hash types**: Tests pHash, aHash, and dHash
3. **Identical images**: Confirms identical images are detected as duplicates
4. **Different images**: Confirms different images are not false positives
5. **Similarity threshold**: Tests threshold behavior
6. **S3 duplicate detection**: Mocked S3 tests for finding duplicates
7. **Metadata enrichment**: Tests enrichment when metadata is missing
8. **Skip enrichment**: Tests that existing metadata is preserved

## Performance Considerations

### Hash Calculation

- **Perceptual hash**: ~10-50ms per image (depends on size)
- **Average hash**: ~5-20ms per image
- **Difference hash**: ~5-20ms per image

### S3 Duplicate Search

- **Time complexity**: O(n) where n = number of objects in bucket
- **Optimization**: Uses pagination to handle large buckets
- **Recommendation**: For buckets with >10,000 images, consider implementing a hash index (DynamoDB, Redis, etc.)

### Memory Usage

- Minimal: Hashes are small (16 bytes for 8x8 hash)
- No image data is kept in memory after processing

## Troubleshooting

### Duplicates Not Detected

1. Check that `ENABLE_DUPLICATE_DETECTION=true`
2. Verify `SIMILARITY_THRESHOLD` is appropriate (try increasing it)
3. Check logs for hash calculation errors
4. Ensure `imagehash` library is installed

### Metadata Not Enriched

1. Check that `ENABLE_METADATA_ENRICHMENT=true`
2. Verify new upload has Skanoteka metadata (companion .txt or .url file)
3. Check that existing duplicate lacks metadata
4. Review logs for enrichment operations

### False Positives

1. Decrease `SIMILARITY_THRESHOLD` (make it more strict)
2. Increase `PERCEPTUAL_HASH_SIZE` for more precision
3. Review the Hamming distances in logs

### False Negatives

1. Increase `SIMILARITY_THRESHOLD` (make it more lenient)
2. Check if images are too different (different content, not just compression)
3. Verify hash calculation succeeded (check logs)

## Dependencies

New dependencies added:

```
imagehash>=4.3.1  # Perceptual image hashing
Pillow>=10.0.0    # Already present, used by imagehash
```

## Migration Guide

### Existing Deployments

1. **Update requirements**: `pip install -r requirements.txt`
2. **Set environment variables**: Add new config vars to `.env`
3. **Deploy updated code**: Standard deployment process
4. **Monitor logs**: Watch for duplicate detection and enrichment events

### Backfilling Hashes

Existing S3 objects won't have perceptual hashes. To backfill:

1. Create a script to iterate through existing objects
2. Download each image
3. Calculate perceptual hashes
4. Update S3 metadata using `enrich_metadata()`

Example backfill script structure:

```python
for obj in s3.list_objects(bucket):
    # Download image
    # Calculate hashes
    # Update metadata
    uploader.enrich_metadata(obj.uri, hashes, overwrite=False)
```

## Future Enhancements

Potential improvements:

1. **Hash Index**: Store hashes in DynamoDB/Redis for O(1) lookups
2. **Batch Processing**: Process multiple images in parallel
3. **Advanced Algorithms**: Add wavelet hash, color hash
4. **Duplicate Groups**: Track groups of similar images
5. **Web UI**: Dashboard for reviewing duplicates
6. **Automatic Deduplication**: Option to automatically delete duplicates

## References

- [imagehash Library](https://github.com/JohannesBuchner/imagehash)
- [Perceptual Hashing](https://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html)
- [Average Hash Algorithm](http://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html)
- [Difference Hash](http://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html)

## Support

For issues or questions:

1. Check logs for error messages
2. Review this documentation
3. Run test suite to verify functionality
4. Check S3 metadata to confirm hashes are being stored

## License

Same as parent project.
