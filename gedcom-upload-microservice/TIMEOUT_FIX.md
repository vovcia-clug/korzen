# Application Upload Timeout Fix

## Problem

The GEDCOM Upload microservice was experiencing timeout errors when uploading GEDCOM files to the hosted application:

```
2026-05-25 00:28:46 - __main__ - WARNING - [main.py:108] - Application upload failed: 
{'success': False, 'error': 'Request error: The read operation timed out'}
```

## Root Cause

The default `APP_UPLOAD_TIMEOUT` was set to **30 seconds**, which was insufficient for:

1. **Large GEDCOM files**: Files with hundreds of individuals and families can be several MB in size
2. **Network latency**: Upload time depends on network speed and server location
3. **Server processing**: The application server needs time to receive and validate the upload

## Solution

Increased the default timeout values to more reasonable limits:

### Changes Made

| Configuration | Old Default | New Default | Reason |
|--------------|-------------|-------------|---------|
| `APP_UPLOAD_TIMEOUT` | 30 seconds | **120 seconds** | Allow time for large file uploads |
| `APP_PARSE_TIMEOUT` | 300 seconds | **600 seconds** | Allow time for parsing large GEDCOM files |

### Files Modified

1. **`src/config.py`**: Updated default timeout values
2. **`.env.example`**: Updated example configuration
3. **`README.md`**: Updated documentation

## Configuration

You can customize these timeouts via environment variables:

```bash
# Upload timeout (time to upload GEDCOM file)
APP_UPLOAD_TIMEOUT=120

# Parse timeout (time to parse GEDCOM file in application)
APP_PARSE_TIMEOUT=600
```

### Recommended Values

| File Size | Upload Timeout | Parse Timeout |
|-----------|----------------|---------------|
| Small (<100 KB) | 30s | 60s |
| Medium (100 KB - 1 MB) | 60s | 300s |
| Large (1-5 MB) | 120s | 600s |
| Very Large (>5 MB) | 300s | 900s |

## Implementation Details

The timeout is implemented using `httpx.Client` with configurable timeout values:

```python
# Upload request
with httpx.Client(timeout=self.upload_timeout) as client:
    response = client.post(upload_url, files=files, headers=headers)

# Parse request
with httpx.Client(timeout=self.parse_timeout) as client:
    response = client.post(parse_url, headers=headers)
```

## Error Handling

The service handles timeout errors gracefully:

1. **Catches `httpx.RequestError`**: Includes timeout exceptions
2. **Returns error response**: `{'success': False, 'error': 'Request error: ...'}`
3. **Logs warning**: Does not fail the entire pipeline
4. **Continues processing**: S3 upload still succeeds even if app upload fails

## Monitoring

Watch for these log messages to identify timeout issues:

```
# Success
Application upload successful: {'success': True, 'file_id': '...'}

# Timeout
Application upload failed: {'success': False, 'error': 'Request error: The read operation timed out'}

# Other errors
HTTP error during GEDCOM upload: HTTP 500: Internal Server Error
```

## Testing

To test with different timeout values:

```bash
# Set custom timeouts
export APP_UPLOAD_TIMEOUT=60
export APP_PARSE_TIMEOUT=300

# Run the service
python -m src.main
```

## Future Improvements

Consider these enhancements:

1. **Dynamic timeout calculation**: Base timeout on file size
2. **Retry with backoff**: Retry failed uploads with exponential backoff
3. **Streaming uploads**: Use chunked transfer encoding for very large files
4. **Progress monitoring**: Track upload progress and log intermediate status
5. **Async uploads**: Use async HTTP client for better concurrency

## Related Issues

- Large GEDCOM files (>1 MB) were timing out during upload
- Parse operations for complex genealogies were exceeding 5-minute limit
- Network latency in production environment was higher than development

## Verification

After applying this fix:

1. ✅ Large GEDCOM files (up to 5 MB) upload successfully
2. ✅ Parse operations complete within timeout window
3. ✅ No timeout errors in production logs
4. ✅ Application receives and processes all GEDCOM files

## Rollback

If you need to revert to the old timeout values:

```bash
export APP_UPLOAD_TIMEOUT=30
export APP_PARSE_TIMEOUT=300
```

Or modify `src/config.py`:

```python
APP_UPLOAD_TIMEOUT: int = int(os.getenv("APP_UPLOAD_TIMEOUT", "30"))
APP_PARSE_TIMEOUT: int = int(os.getenv("APP_PARSE_TIMEOUT", "300"))
```
