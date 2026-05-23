# Recursive Scan Feature

## Overview

The image upload microservice includes the following features:

1. **Recursive Directory Scanning**: Descends into subdirectories to find all image files
2. **Initial Startup Scan**: Scans all existing files on startup (not just new files)
3. **File Hashing**: Calculates SHA-256 hash for each file
4. **Directory Structure Preservation**: Maintains original directory structure in S3 keys

## Features

### 1. Recursive Directory Scanning

The service recursively scans subdirectories when `WATCH_RECURSIVE=true` (default is `true`).

**Configuration:**
```bash
WATCH_RECURSIVE=true  # Enable recursive subdirectory monitoring (default: true)
```

**Behavior:**
- Monitors all subdirectories within the watch directory
- Detects new files in any subdirectory
- Processes files regardless of directory depth
- Preserves directory structure in S3 uploads

### 2. Initial Startup Scan

On startup, the service scans all existing files in the watch directory (and subdirectories if recursive mode is enabled).

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
- Hash is calculated during image validation in [`ImageDetector`](src/services/image_detector.py)
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

### 4. Directory Structure Preservation

The service preserves the original directory structure when uploading to S3.

**Implementation:**
- The [`S3Uploader.generate_s3_key()`](src/services/s3_uploader.py) method accepts a `base_directory` parameter
- Calculates relative path from base directory
- Includes directory structure in S3 key

**Example:**
```
Local file:  /watched-images/2024/january/scan001.jpg
S3 key:      uploads/2024/january/uuid-scan001.jpg
```

## Configuration

### Environment Variables

```bash
# Enable recursive directory monitoring (default: true)
WATCH_RECURSIVE=true

# Watch directory path
WATCH_DIRECTORY=/app/watched-images

# S3 configuration
S3_BUCKET=my-genealogy-images
S3_PREFIX=uploads/

# Post-upload action
POST_UPLOAD_ACTION=keep  # or 'archive' or 'delete'
ARCHIVE_DIRECTORY=/app/processed-images
```

## Use Cases

### Use Case 1: Batch Upload Existing Files

You have a directory with thousands of existing images that need to be uploaded:

1. Configure the service with your directory
2. Start the service
3. Service automatically scans and uploads all files
4. Monitor progress via logs

### Use Case 2: Organized Directory Structure

You have images organized in subdirectories by date, location, or category:

```
watched-images/
├── 2024/
│   ├── january/
│   │   ├── scan001.jpg
│   │   └── scan002.jpg
│   └── february/
│       └── scan003.jpg
└── 2025/
    └── march/
        └── scan004.jpg
```

The service will:
1. Recursively scan all subdirectories
2. Upload each file to S3
3. Preserve the directory structure in S3 keys
4. Send SQS notifications for each file

### Use Case 3: Continuous Monitoring

The service continuously monitors for new files:

1. Service runs in background
2. New files added to any subdirectory are detected
3. Files are automatically uploaded
4. Directory structure is preserved

## Implementation Details

### Initial Scan Logic

Located in [`src/main.py`](src/main.py):

```python
def scan_existing_files(
    directory: Path,
    orchestrator: UploadOrchestrator,
    supported_extensions: set,
    recursive: bool = False
) -> int:
    """Scan directory for existing files and process them."""
    # Recursively or non-recursively scan directory
    # Process each valid image file
    # Return count of files found
```

### Directory Structure Preservation

Located in [`src/services/s3_uploader.py`](src/services/s3_uploader.py):

```python
def generate_s3_key(self, file_path: Path, base_directory: Optional[Path] = None) -> str:
    """Generate S3 object key for file, preserving directory structure."""
    # Calculate relative path from base_directory
    # Generate unique filename with UUID
    # Combine prefix + relative path + unique filename
```

### Recursive Watching

Located in [`src/services/directory_watcher.py`](src/services/directory_watcher.py):

The `DirectoryWatcher` uses `watchdog.observers.Observer` with recursive flag to monitor subdirectories.

## Performance Considerations

### Large Directory Scans

For directories with many files:

1. **Startup Time**: Initial scan may take time for large directories
2. **Memory Usage**: File list is processed iteratively (not loaded all at once)
3. **Logging**: Progress is logged for monitoring

**Recommendations:**
- Use `LOG_LEVEL=INFO` to track progress
- Monitor memory usage for very large directories
- Consider batch processing for millions of files

### Recursive Watching

Recursive watching has minimal overhead:
- `watchdog` library efficiently monitors subdirectories
- Event filtering reduces unnecessary processing
- Debouncing prevents duplicate events

## Troubleshooting

### Files Not Being Detected

**Problem**: Files in subdirectories are not processed

**Solutions:**
1. Verify `WATCH_RECURSIVE=true` is set
2. Check file extensions are in `SUPPORTED_EXTENSIONS`
3. Ensure subdirectories are readable
4. Check logs for validation errors

### Initial Scan Taking Too Long

**Problem**: Startup scan is slow for large directories

**Solutions:**
1. This is expected for large directories
2. Monitor progress via logs
3. Consider splitting into smaller directories
4. Ensure adequate system resources

### Directory Structure Not Preserved

**Problem**: S3 keys don't reflect directory structure

**Solutions:**
1. Verify the upload logic is passing `base_directory` parameter
2. Check S3 keys in logs
3. Review S3 bucket contents

## Statistics

The service tracks processing statistics:

```python
{
    "files_processed": 100,
    "files_uploaded": 98,
    "files_failed": 2,
    "validation_failures": 1,
    "upload_failures": 0,
    "notification_failures": 0,
    "metadata_extracted": 85,
}
```

Access statistics via logs:
```
INFO - periodic_statistics - files_processed=100 - files_uploaded=98 - ...
```

## Related Documentation

- [`src/main.py`](src/main.py) - Entry point with initial scan
- [`src/services/s3_uploader.py`](src/services/s3_uploader.py) - S3 upload with directory preservation
- [`src/services/upload_orchestrator.py`](src/services/upload_orchestrator.py) - Upload workflow coordination
- [`src/services/directory_watcher.py`](src/services/directory_watcher.py) - Recursive directory monitoring
- [`README.md`](README.md) - User documentation
- [`ARCHITECTURE.md`](ARCHITECTURE.md) - Technical architecture
