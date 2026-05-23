# Optional Page Number Fix

## Problem

The `gedcom-generation-microservice` was failing with the error:
```
ValueError: Message parsing failed: Missing 'page_number' in metadata
```

This occurred when processing messages from the OCR microservice that didn't have a `page_number` field in their metadata. This could happen when:

1. Images are uploaded without page number information in the filename or S3 path
2. Single-page documents that don't need page numbering
3. The OCR microservice cannot extract page numbers from the S3 URI or tags

## Solution

Made `page_number` an **optional** field throughout the gedcom-generation-microservice. The service now gracefully handles messages with or without page numbers.

## Changes Made

### 1. [`sqs_consumer.py`](src/services/sqs_consumer.py)
- **Line 136-144**: Changed from raising an error to logging a warning when `page_number` is missing
- Sets `page_number` to `None` instead of failing
- Allows processing to continue for single-page or unnumbered documents

### 2. [`document_grouper.py`](src/services/document_grouper.py)
- **Line 42-56**: Updated `get_sorted_messages()` to handle `None` page numbers
  - Messages with `None` page numbers are sorted to the end
  - Uses tuple sorting: `(is_none, page_number or 0)`
- **Line 49-56**: Updated `get_page_numbers()` return type to `List[Optional[int]]`
  - Now explicitly returns `None` values instead of converting to `0`

### 3. [`metadata_formatter.py`](src/services/metadata_formatter.py)
- **Line 108-124**: Updated page formatting to handle missing page numbers
  - If `page_number` is available, displays it normally
  - If `page_number` is `None`, displays as "X (page number unknown)" where X is the sequential index
  - Ensures readable output even without page numbers

### 4. [`main.py`](src/main.py)
- **Line 204-220**: Updated missing page detection logic
  - Filters out `None` values before checking for missing pages
  - Only validates page completeness when valid page numbers exist
  - Logs a warning if no valid page numbers are available

## Behavior

### With Page Numbers (Normal Case)
```
PAGE 1:
[OCR content]

PAGE 2:
[OCR content]
```

### Without Page Numbers (New Case)
```
PAGE 1 (page number unknown):
[OCR content]

PAGE 2 (page number unknown):
[OCR content]
```

## Benefits

1. **Robustness**: Service no longer crashes on messages without page numbers
2. **Flexibility**: Supports both multi-page documents and single-page images
3. **Backward Compatible**: Existing messages with page numbers work exactly as before
4. **Clear Logging**: Warnings indicate when page numbers are missing for debugging

## Testing Recommendations

1. Test with messages that have valid page numbers (existing behavior)
2. Test with messages missing page numbers (new behavior)
3. Test with mixed documents (some pages with numbers, some without)
4. Verify GEDCOM generation works correctly in all cases

## Related Files

- `ocr-image-microservice/src/services/metadata_extractor.py` - Extracts page numbers from S3 paths/tags
- `ocr-image-microservice/src/services/sqs_publisher.py` - Publishes messages with metadata
- `image-upload-microservice/src/services/sqs_notifier.py` - Initial message source
