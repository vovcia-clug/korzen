# Message Acknowledgment Fix

## Problem

The gedcom-upload-microservice was marking SQS messages as processed (deleting them from the queue) even when the application upload failed or timed out. This caused data loss as failed uploads were never retried.

### Symptoms

From the logs:
```
gedcom-upload-microservice  | Request error during GEDCOM upload: Request error: The read operation timed out
gedcom-upload-microservice  | 2026-05-25 14:59:39 - __main__ - WARNING - [main.py:108] - Application upload failed: {'success': False, 'error': 'Request error: The read operation timed out'}
gedcom-upload-microservice  | 2026-05-25 14:59:39 - __main__ - INFO - [main.py:114] - Message cf2a7f2f-9e8b-4ed1-910b-913b1acd2e01 processed successfully - S3: s3://korzen-ocr-results/gedcom-files/2472-3633.ged, App: False
```

The message was marked as "processed successfully" and deleted from the queue despite the application upload failing.

## Root Cause

In [`main.py`](src/main.py:105-123), the code had the following issues:

1. **Timeout too short**: Default upload timeout was 30 seconds, but parsing large GEDCOM files can take much longer
2. **Error handling**: Application upload failures were logged as warnings but didn't fail the message processing
3. **Premature acknowledgment**: Messages were deleted from the queue regardless of application upload success

```python
# OLD CODE (lines 105-123)
if app_result.get("success"):
    logger.info(f"Application upload successful: {app_result}")
else:
    logger.warning(f"Application upload failed: {app_result}")
    # Don't fail the entire process if app upload fails  # ❌ WRONG!

# Log final results
logger.info(
    f"Message {message_id} processed successfully - "
    f"S3: {s3_uri}, "
    f"App: {app_result.get('success') if app_result else 'skipped'}"
)

# Delete message from queue
sqs_consumer.delete_message(receipt_handle)  # ❌ Always deleted!

return True  # ❌ Always returned success!
```

## Solution

### 1. Changed Error Handling

Modified [`main.py`](src/main.py:91-121) to fail the message processing when application upload fails:

```python
# NEW CODE
if Config.APP_UPLOAD_ENABLED:
    if not gedcom_content:
        logger.error("Cannot upload to application: no GEDCOM content available")
        return False  # ✅ Fail the message processing
    else:
        logger.info("Uploading GEDCOM to hosted application...")
        app_result = app_uploader.upload_and_parse(
            gedcom_content=gedcom_content,
            filename=filename,
            document_id=document_id,
            auto_parse=Config.APP_AUTO_PARSE
        )
        
        if app_result.get("success"):
            logger.info(f"Application upload successful: {app_result}")
        else:
            logger.error(f"Application upload failed: {app_result}")
            return False  # ✅ Fail so message can be retried
```

### 2. Message Acknowledgment

The message is now only deleted from the queue when the function returns `True`, which only happens after successful application upload (when enabled).

### 3. Retry Behavior

When `process_message()` returns `False`:
- The message is NOT deleted from the queue
- SQS will automatically make the message visible again after the visibility timeout (300 seconds)
- The message will be retried up to `MAX_RETRIES` times (default: 3)
- If all retries fail, the message goes to the Dead Letter Queue (if configured)

## Configuration

### Timeout Settings

The default timeouts in [`config.py`](src/config.py:32-33) are:

```python
APP_UPLOAD_TIMEOUT: int = int(os.getenv("APP_UPLOAD_TIMEOUT", "120"))  # 2 minutes for upload
APP_PARSE_TIMEOUT: int = int(os.getenv("APP_PARSE_TIMEOUT", "600"))   # 10 minutes for parsing
```

These can be adjusted via environment variables if needed:

```bash
# For very large GEDCOM files that take longer to parse
APP_PARSE_TIMEOUT=900  # 15 minutes
```

### SQS Visibility Timeout

The SQS visibility timeout should be set higher than the total processing time:

```python
SQS_VISIBILITY_TIMEOUT: int = int(os.getenv("SQS_VISIBILITY_TIMEOUT", "300"))  # 5 minutes
```

**Recommendation**: Set this to at least `APP_UPLOAD_TIMEOUT + APP_PARSE_TIMEOUT + buffer`:

```bash
SQS_VISIBILITY_TIMEOUT=900  # 15 minutes (120 + 600 + 180 buffer)
```

## Impact

### Before Fix
- ❌ Failed uploads were lost forever
- ❌ Messages deleted even on timeout
- ❌ No automatic retry mechanism
- ❌ Silent data loss

### After Fix
- ✅ Failed uploads are automatically retried
- ✅ Messages only deleted on success
- ✅ Proper error propagation
- ✅ No data loss

## Testing

To verify the fix works:

1. **Simulate timeout**: Set a very short timeout and verify message is retried
   ```bash
   APP_PARSE_TIMEOUT=5  # 5 seconds (will timeout)
   ```

2. **Check logs**: Failed uploads should now show ERROR level and message should not be deleted
   ```
   ERROR - Application upload failed: {'success': False, 'error': '...'}
   ```

3. **Verify retry**: The same message should be processed again after visibility timeout

4. **Check DLQ**: After max retries, message should go to Dead Letter Queue (if configured)

## Related Files

- [`src/main.py`](src/main.py) - Main message processing logic
- [`src/config.py`](src/config.py) - Configuration and timeout settings
- [`src/services/application_uploader.py`](src/services/application_uploader.py) - Application upload implementation
- [`src/services/sqs_consumer.py`](src/services/sqs_consumer.py) - SQS message handling

## Migration Notes

No migration needed. The fix is backward compatible and will take effect immediately when deployed.

However, consider:
1. Reviewing and adjusting timeout values based on your GEDCOM file sizes
2. Configuring a Dead Letter Queue for messages that fail after all retries
3. Setting up CloudWatch alarms for repeated failures
