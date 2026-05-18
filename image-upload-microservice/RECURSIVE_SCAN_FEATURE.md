# Recursive Scan and Duplicate Detection Features

## Overview

The image upload microservice has been enhanced with the following features:

1. **Recursive Directory Scanning**: Descends into subdirectories to find all image files
2. **Initial Startup Scan**: Scans all existing files on startup (not just new files)
3. **File Hashing**: Calculates SHA-256 hash for each file
4. **S3 Duplicate Detection**: Checks if file already exists in S3 before uploading

## New Features

### 1. Recursive Directory Scanning

The service now recursively scans subdirectories when `WATCH_RECURSIVE=true` (default is now `true`).

**Configuration:**
```bash
WATCH_RECURSIVE=true  # Enable recursive subdirectory monitoring (default: true)
```

**Behavior:**
- Monitors all subdirectories within the watch directory
- Detects new files in any subdirectory
- Processes files regardless of directory depth

### 2. Initial Startup Scan

On startup, the service now scans all existing files in the watch directory (and subdirectories if recursive mode is enabled).

**Benefits:**
- Processes files that were added while the service was offline
- No manual intervention needed to upload existing files
- Automatically catches up with backlog

**Log Messages:**
```
INFO - starting_initial_directory_scan - directory=/path/to/watch
INFO - initial_scan_file_found - file=/path/to/image.jpg
INFO - initial_scan_completed - files_found=42
```

### 3. File Hashing (SHA-256)

Each file is automatically hashed using SHA-256 algorithm during validation.

**Implementation:**
- Hash is calculated during image validation in [`ImageDetector`](src/services/image_detector.py:178)
- Hash is stored in file metadata
- Hash is attached to S3 object metadata (key: `file-hash`)

**Metadata Structure:**
```python
{
    "file_hash": {
        "algorithm": "sha256",
        "value": "a1b2c3d4e5f6..."
    }
}
```

### 4. S3 Duplicate Detection

Before uploading, the service checks if a file with the same hash already exists in S3.

**Two-Level Duplicate Detection:**

1. **In-Memory Check**: Fast check against recently processed files in current session
2. **S3 Check**: Queries S3 bucket for existing objects with matching hash

**Implementation Details:**

The [`S3Uploader.object_exists_by_hash()`](src/services/s3_uploader.py:277) method:
- Lists objects in the S3 bucket with the configured prefix
- Checks the `file-hash` metadata of each object
- Returns S3 URI if duplicate found, `None` otherwise

The [`UploadOrchestrator`](src/services/upload_orchestrator.py:122) uses duplicate detection:
- First checks in-memory hash set
- Then checks S3 if not found in memory
- Skips upload if duplicate detected
- Still performs post-upload action (archive/delete) if configured

**Log Messages:**
```
INFO - file_duplicate_skipped_memory - file=/path/to/image.jpg - hash=abc123...
INFO - file_duplicate_skipped_s3 - file=/path/to/image2.jpg - hash=abc123... - existing_s3_uri=s3://bucket/path/file.jpg
```

## Performance Considerations

### S3 Duplicate Check Performance

The S3 duplicate check uses pagination to handle large buckets:
- Iterates through all objects in the bucket prefix
- Fetches metadata for each object (head_object)
- May be slow for buckets with millions of objects

**Optimization Recommendations:**

1. **Use specific S3 prefix**: Configure `S3_PREFIX` to narrow search scope
2. **Consider alternative indexing**: For very large deployments, consider using:
   - DynamoDB table mapping hash → S3 URI
   - ElastiCache/Redis for faster lookups
   - Lambda function triggered on S3 PUT to build index

### Initial Scan Performance

For directories with thousands of files:
- Files are processed synchronously during startup
- Service becomes ready after scan completes
- Consider processing in background thread for large directories

## Configuration

### Environment Variables

```bash
# Directory watching
WATCH_DIRECTORY=/app/watched-images
WATCH_RECURSIVE=true  # NEW DEFAULT: true (was false)

# S3 configuration
S3_BUCKET=my-genealogy-images
S3_PREFIX=uploads/  # Used to scope duplicate detection

# Post-upload actions
POST_UPLOAD_ACTION=keep  # keep|archive|delete
ARCHIVE_DIRECTORY=/app/archived  # Required if action=archive
```

## Example Use Cases

### Use Case 1: Catch-Up Mode
You have 1000 historical images in a directory. Start the service and it will:
1. Scan all 1000 files on startup
2. Hash each file
3. Check S3 for duplicates
4. Upload only new files
5. Begin monitoring for new files

### Use Case 2: Multiple Sources
You have multiple directories with potentially duplicate images:
1. Point service at first directory
2. All unique images uploaded
3. Point service at second directory
4. Duplicate images automatically skipped based on hash
5. Only new images uploaded

### Use Case 3: Nested Directory Structure
Your image archive has this structure:
```
genealogy/
  ├── parish_a/
  │   ├── 1800/
  │   ├── 1801/
  ├── parish_b/
  │   ├── 1800/
  │   └── 1801/
```

With `WATCH_RECURSIVE=true`, all files in all subdirectories are:
- Discovered on startup
- Monitored for changes
- Uploaded to S3 with hash-based deduplication

## API Changes

### S3Uploader

New method:
```python
def object_exists_by_hash(self, file_hash: str) -> Optional[str]:
    """Check if an object with the given hash exists in S3.
    
    Returns S3 URI if found, None otherwise.
    """
```

### UploadOrchestrator

Enhanced duplicate detection in `process_file()`:
- Checks in-memory hash set
- Calls `s3_uploader.object_exists_by_hash()`
- Skips upload if duplicate found in either location

### Main Entry Point

New function:
```python
def scan_existing_files(
    directory: Path,
    orchestrator: UploadOrchestrator,
    supported_extensions: set,
    recursive: bool = False
) -> int:
    """Scan directory for existing files and process them."""
```

## Migration Guide

### Updating from Previous Version

1. **No breaking changes**: Service remains backward compatible
2. **New default behavior**: `WATCH_RECURSIVE` now defaults to `true`
3. **Initial scan**: Service will scan existing files on first startup with new version

### Recommended Steps

1. Update environment variables if needed:
   ```bash
   # Explicitly set if you don't want recursive scanning
   WATCH_RECURSIVE=false
   ```

2. Review S3 prefix configuration:
   ```bash
   # Set specific prefix to scope duplicate detection
   S3_PREFIX=uploads/genealogy/
   ```

3. Monitor initial startup:
   ```bash
   docker-compose logs -f image-upload-microservice
   # Watch for "initial_scan_completed" message
   ```

4. Verify duplicate detection:
   - Check logs for "file_duplicate_skipped_s3" messages
   - Confirm no duplicate uploads in S3 bucket

## Troubleshooting

### Initial Scan Takes Too Long

**Problem**: Service takes minutes to start with large directories

**Solutions:**
- Reduce `WATCH_DIRECTORY` scope
- Process subdirectories separately
- Consider background scan implementation

### S3 Duplicate Check Slow

**Problem**: Upload pipeline slow due to S3 checks

**Solutions:**
- Set more specific `S3_PREFIX`
- Implement external hash index (DynamoDB/Redis)
- Adjust S3 pagination settings

### False Duplicate Detection

**Problem**: Different files marked as duplicates

**Solution**: This shouldn't happen with SHA-256, but check:
- S3 metadata is being written correctly
- Hash calculation is deterministic
- No hash collisions (extremely unlikely with SHA-256)

## Future Enhancements

Potential improvements for future versions:

1. **Background Initial Scan**: Scan in background thread, start watching immediately
2. **Hash Index Service**: Separate service for fast hash lookups
3. **Progress Reporting**: API endpoint showing scan/upload progress
4. **Batch Processing**: Process initial scan in batches with rate limiting
5. **Smart Retry**: Retry failed S3 checks with exponential backoff
6. **Metrics**: Prometheus metrics for scan performance and duplicate rate

## Related Files

- [`src/main.py`](src/main.py) - Entry point with initial scan
- [`src/services/s3_uploader.py`](src/services/s3_uploader.py) - S3 duplicate detection
- [`src/services/upload_orchestrator.py`](src/services/upload_orchestrator.py) - Duplicate checking logic
- [`src/services/image_detector.py`](src/services/image_detector.py) - File hashing
- [`src/config.py`](src/config.py) - Configuration with new defaults
