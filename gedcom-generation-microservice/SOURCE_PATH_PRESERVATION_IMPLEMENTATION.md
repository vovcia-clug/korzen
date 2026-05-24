# Source Path Preservation Implementation

## Overview
This document describes the implementation of source path preservation in the gedcom-generation-microservice to ensure GEDCOM files are uploaded to S3 with the same directory structure as the original source images.

## Problem Statement
The gedcom-generation-microservice was uploading all GEDCOM files to a flat directory structure under the configured S3 prefix (e.g., `gedcom-files/`), regardless of the original source image directory structure. This made it difficult to maintain organization and trace GEDCOM files back to their source images.

## Solution
Implemented directory structure preservation similar to the ocr-image-microservice pattern, where output files maintain the same directory hierarchy as their source files.

## Changes Made

### 1. Updated `s3_handler.py`
**File:** [`gedcom-generation-microservice/src/services/s3_handler.py`](gedcom-generation-microservice/src/services/s3_handler.py)

**Changes:**
- Added `source_s3_uri` parameter to `upload_gedcom()` method
- Added `preserve_structure` parameter (default: `True`)
- Implemented path parsing logic to extract directory structure from source S3 URI
- Preserves parent directory path when uploading GEDCOM files

**Example:**
```python
# Before:
# Source: s3://bucket/documents/parish-123/page-001.jpg
# GEDCOM: s3://bucket/gedcom-files/parish-123.ged

# After:
# Source: s3://bucket/documents/parish-123/page-001.jpg
# GEDCOM: s3://bucket/gedcom-files/documents/parish-123/parish-123.ged
```

### 2. Updated `main.py`
**File:** [`gedcom-generation-microservice/src/main.py`](gedcom-generation-microservice/src/main.py)

**Changes:**
- Modified `process_complete_document()` to extract source image URI from first message
- Updated `_upload_to_s3()` method signature to accept `source_image_uri` parameter
- Passes source image URI to S3 handler with `preserve_structure=True`

**Code Flow:**
1. Extract first source image URI from sorted messages: `sorted_messages[0].get("source_image", {}).get("s3_uri")`
2. Pass to `_upload_to_s3()` method
3. S3 handler parses source URI and preserves directory structure

## Comparison with Other Microservices

### OCR Image Microservice Pattern
The ocr-image-microservice implements similar functionality in [`ocr-image-microservice/src/services/s3_handler.py`](ocr-image-microservice/src/services/s3_handler.py:162-240):

```python
def upload_result(
    self,
    content: str,
    s3_uri: str,
    output_prefix: str,
    file_extension: str = ".md",
    preserve_structure: bool = True
) -> str:
    # Preserves directory structure from source if preserve_structure=True
    if preserve_structure:
        original_path = Path(original_key)
        base_name = original_path.stem
        parent_path = original_path.parent
        
        if str(parent_path) != '.':
            output_key = f"{output_prefix}{parent_path}/{base_name}{file_extension}"
```

### Image Upload Microservice
The image-upload-microservice preserves structure when uploading to S3 via the `base_directory` parameter in [`image-upload-microservice/src/services/upload_orchestrator.py`](image-upload-microservice/src/services/upload_orchestrator.py:136-140).

### GEDCOM Upload Microservice
The gedcom-upload-microservice receives GEDCOM files that already have S3 URIs from the generation service, so it doesn't need to implement path preservation - it uses the URIs as-is.

## Message Flow with Source Path Preservation

### Complete Pipeline:
1. **image-upload-microservice** → Uploads image to S3
   - Input: Local file at `/path/to/documents/parish-123/page-001.jpg`
   - Output: `s3://bucket/images/documents/parish-123/page-001.jpg`
   - Message: `{"s3_uri": "s3://bucket/images/documents/parish-123/page-001.jpg"}`

2. **ocr-image-microservice** → Processes image and preserves structure
   - Input: `s3://bucket/images/documents/parish-123/page-001.jpg`
   - Output: `s3://bucket/ocr-results/documents/parish-123/page-001.md`
   - Message: 
     ```json
     {
       "source_image": {"s3_uri": "s3://bucket/images/documents/parish-123/page-001.jpg"},
       "ocr_result": {"s3_uri": "s3://bucket/ocr-results/documents/parish-123/page-001.md"}
     }
     ```

3. **gedcom-generation-microservice** → Generates GEDCOM and preserves structure ✅ **NEW**
   - Input: Multiple OCR messages for document `parish-123`
   - Source: `s3://bucket/images/documents/parish-123/page-001.jpg` (from first message)
   - Output: `s3://bucket/gedcom-files/documents/parish-123/parish-123.ged`
   - Message:
     ```json
     {
       "gedcom_data": {"s3_uri": "s3://bucket/gedcom-files/documents/parish-123/parish-123.ged"},
       "source_ocr_uris": ["s3://bucket/ocr-results/documents/parish-123/page-001.md", ...],
       "source_image_uris": ["s3://bucket/images/documents/parish-123/page-001.jpg", ...]
     }
     ```

4. **gedcom-upload-microservice** → Uses existing S3 URI
   - Input: GEDCOM ready message with S3 URI
   - Action: Downloads from existing URI or uploads to application

## Benefits

1. **Organizational Consistency**: GEDCOM files maintain the same directory structure as source images
2. **Traceability**: Easy to trace GEDCOM files back to their source images by path
3. **Scalability**: Works with any directory depth and structure
4. **Compatibility**: Follows the same pattern as ocr-image-microservice
5. **Backward Compatibility**: Falls back to simple prefix if source URI is not provided or parsing fails

## Configuration

The feature is controlled by the `preserve_structure` parameter in the S3 handler:
- **Default**: `True` (preserve directory structure)
- **Fallback**: If source URI is missing or parsing fails, uses simple prefix

## Testing Recommendations

1. **Test with nested directories**: Verify structure is preserved for deep paths
2. **Test with flat structure**: Verify works when source has no parent directories
3. **Test with missing source URI**: Verify fallback to simple prefix works
4. **Test with malformed URIs**: Verify error handling and fallback behavior
5. **Test with different S3 URI formats**: Verify parsing works for s3://, ARN, and HTTPS formats

## Example Scenarios

### Scenario 1: Nested Directory Structure
```
Source Image:  s3://bucket/archives/poland/krakow/parish-records/1850-1900/baptisms/page-001.jpg
OCR Result:    s3://bucket/ocr-results/archives/poland/krakow/parish-records/1850-1900/baptisms/page-001.md
GEDCOM Output: s3://bucket/gedcom-files/archives/poland/krakow/parish-records/1850-1900/baptisms/parish-records-1850-1900-baptisms.ged
```

### Scenario 2: Flat Structure
```
Source Image:  s3://bucket/page-001.jpg
OCR Result:    s3://bucket/ocr-results/page-001.md
GEDCOM Output: s3://bucket/gedcom-files/document-123.ged
```

### Scenario 3: Collection-Based Structure (Skanoteka)
```
Source Image:  s3://bucket/collections/3500/scans/0001.jpg
OCR Result:    s3://bucket/ocr-results/collections/3500/scans/0001.md
GEDCOM Output: s3://bucket/gedcom-files/collections/3500/scans/3500.ged
```

## Implementation Notes

1. **Path Parsing**: Uses Python's `pathlib.Path` for robust path manipulation
2. **Error Handling**: Comprehensive try-catch blocks with fallback to simple prefix
3. **Logging**: Detailed logging for debugging path preservation logic
4. **URI Format Support**: Handles s3:// format (primary), with warnings for other formats
5. **First Message Strategy**: Uses the first message's source image URI as the reference for directory structure

## Future Enhancements

1. **Configuration Option**: Add environment variable to enable/disable structure preservation
2. **Custom Path Mapping**: Allow custom path transformation rules
3. **Validation**: Add validation to ensure all messages in a document group have consistent paths
4. **Metrics**: Track structure preservation success/failure rates

## Related Files

- [`gedcom-generation-microservice/src/services/s3_handler.py`](gedcom-generation-microservice/src/services/s3_handler.py) - S3 upload logic
- [`gedcom-generation-microservice/src/main.py`](gedcom-generation-microservice/src/main.py) - Main service orchestration
- [`ocr-image-microservice/src/services/s3_handler.py`](ocr-image-microservice/src/services/s3_handler.py) - Reference implementation
