# OCR Image Microservice Refactoring Summary

## Overview

The OCR Image Microservice has been refactored to support JSON metadata loading and Skanoteka tag processing for improved document grouping capabilities.

## Changes Made

### 1. New Service: MetadataJsonLoader

**File**: [`src/services/metadata_json_loader.py`](src/services/metadata_json_loader.py)

A new service that handles loading and parsing JSON metadata files from S3:

- **`load_from_s3()`**: Downloads and parses JSON metadata files
- **`extract_skanoteka_metadata()`**: Extracts Skanoteka-specific fields
- **`_extract_document_id_from_unit()`**: Parses document ID from unit string
- **`_extract_page_number_from_page_field()`**: Extracts page number from page field
- **`_extract_total_pages_from_page_field()`**: Extracts total pages from page field

**Key Features:**
- Automatic JSON file discovery (replaces image extension with .json)
- Skanoteka metadata extraction with pattern matching
- Document ID extraction from unit numbers (e.g., "4500 M-1874-1937" → "4500")
- Page number extraction from page field (e.g., "301.jpg (301 z 303)" → 301)
- Total pages extraction for document completion tracking

### 2. Updated Service: S3Handler

**File**: [`src/services/s3_handler.py`](src/services/s3_handler.py)

**New Method**: `download_json()`
- Downloads JSON metadata files from S3
- Returns None if file not found (404/NoSuchKey)
- Handles errors gracefully

**Updated Method**: `upload_result()`
- Added `preserve_structure` parameter (default: True)
- Preserves directory structure from source S3 URI
- Example: `s3://bucket/uploads/unit_4500/301.jpg` → `s3://bucket/ocr-results/unit_4500/301.md`

### 3. Updated Main Processing Flow

**File**: [`src/main.py`](src/main.py)

**New Processing Steps:**
1. Download image from S3
2. **Load JSON metadata** (new)
3. Extract metadata from S3 path and tags
4. **Process Skanoteka metadata** (new)
5. Perform OCR
6. Upload OCR result to S3 (with structure preservation)
7. Publish to SQS
8. Delete message from input queue

**Metadata Merging Logic:**
- Skanoteka JSON metadata takes precedence over S3 tags and path extraction
- `document_id`, `page_number`, and `total_pages` from Skanoteka override other sources
- Full Skanoteka metadata stored in `metadata['skanoteka']` for downstream use

### 4. New Documentation

**Files Created:**
- [`METADATA_JSON_INTEGRATION.md`](METADATA_JSON_INTEGRATION.md): Comprehensive guide to JSON metadata integration
- [`REFACTORING_SUMMARY.md`](REFACTORING_SUMMARY.md): This file

## Skanoteka Metadata Format

### Input JSON Structure
```json
{
  "place": "Bolechów",
  "unit": "4500 M-1874-1937-Bolechów",
  "years": "1874-1937",
  "page": "301.jpg (301 z 303)"
}
```

### Extracted Metadata
```python
{
    "document_id": "4500",           # From unit field
    "page_number": 301,              # From page field
    "total_pages": 303,              # From page field
    "place": "Bolechów",
    "unit": "4500 M-1874-1937-Bolechów",
    "years": "1874-1937",
    "page": "301.jpg (301 z 303)"
}
```

## Benefits

### 1. Accurate Document Grouping
- **Document ID**: Extracted from Skanoteka unit numbers (e.g., "4500")
- **Page Numbers**: Extracted from page field with pattern matching
- **Total Pages**: Enables completion detection in GEDCOM generation service

### 2. Directory Structure Preservation
- OCR results maintain source directory structure
- Easier organization and batch processing
- Example: `unit_4500/301.jpg` → `unit_4500/301.md`

### 3. Enhanced Metadata
- Full Skanoteka context preserved (place, years, unit)
- Available for downstream GEDCOM generation
- Improves genealogical record accuracy

### 4. Backward Compatibility
- Works with or without JSON metadata
- Falls back to S3 path/tag extraction
- No breaking changes to existing functionality

## Integration with Pipeline

### Upstream: Image Upload Microservice
- Uploads images and companion JSON files to S3
- Preserves directory structure
- Example: `unit_4500/301.jpg` and `unit_4500/301.json`

### Current: OCR Image Microservice
- Loads JSON metadata if available
- Extracts Skanoteka fields
- Performs OCR
- Uploads results with preserved structure
- Publishes enriched metadata to SQS

### Downstream: GEDCOM Generation Microservice
- Receives messages with `document_id`, `page_number`, `total_pages`
- Groups pages by `document_id`
- Orders pages by `page_number`
- Detects completion using `total_pages`
- Generates GEDCOM files with contextual information

## Example Processing Flow

### Input
```
S3: s3://bucket/uploads/unit_4500/301.jpg
S3: s3://bucket/uploads/unit_4500/301.json
```

### Processing
```
1. Download: unit_4500/301.jpg
2. Load JSON: unit_4500/301.json
3. Extract Skanoteka:
   - document_id: "4500"
   - page_number: 301
   - total_pages: 303
4. Perform OCR
5. Upload: s3://bucket/ocr-results/unit_4500/301.md
```

### Output SQS Message
```json
{
  "source_image_uri": "s3://bucket/uploads/unit_4500/301.jpg",
  "ocr_result_uri": "s3://bucket/ocr-results/unit_4500/301.md",
  "metadata": {
    "document_id": "4500",
    "page_number": 301,
    "total_pages": 303,
    "skanoteka": {
      "place": "Bolechów",
      "unit": "4500 M-1874-1937-Bolechów",
      "years": "1874-1937",
      "page": "301.jpg (301 z 303)"
    }
  }
}
```

## Testing

### Unit Tests Needed
- [ ] `metadata_json_loader.py`: Test Skanoteka extraction patterns
- [ ] `s3_handler.py`: Test JSON download and structure preservation
- [ ] `main.py`: Test metadata merging logic

### Integration Tests Needed
- [ ] End-to-end with JSON metadata
- [ ] End-to-end without JSON metadata (fallback)
- [ ] Directory structure preservation
- [ ] Skanoteka page number extraction

### Test Cases
1. **With Skanoteka JSON**: Verify document_id and page_number extraction
2. **Without JSON**: Verify fallback to S3 path extraction
3. **Invalid JSON**: Verify graceful handling
4. **Missing Skanoteka fields**: Verify fallback behavior
5. **Directory structure**: Verify preserved in output

## Configuration

No new configuration required. The feature works automatically when:
- JSON files exist in S3 alongside images
- JSON files contain valid Skanoteka metadata fields

## Error Handling

### JSON Not Found
- Logs info message
- Continues with fallback metadata extraction
- No processing failure

### JSON Parse Error
- Logs warning
- Continues with fallback metadata extraction
- No processing failure

### Missing Skanoteka Fields
- Logs debug message
- Uses fallback metadata extraction
- No processing failure

## Performance Impact

- **Minimal**: One additional S3 GET request per image (only if JSON exists)
- **Optimized**: JSON download returns None on 404 (no retry)
- **Efficient**: JSON parsing is fast (small files)

## Migration Notes

### For Existing Deployments
1. Deploy updated code
2. No configuration changes needed
3. Existing images without JSON continue to work
4. New images with JSON automatically benefit

### For New Deployments
1. Ensure image-upload-microservice uploads JSON files
2. Deploy ocr-image-microservice with refactoring
3. Verify JSON files are being loaded (check logs)
4. Confirm metadata in SQS messages

## Related Documentation

- [METADATA_JSON_INTEGRATION.md](METADATA_JSON_INTEGRATION.md): Detailed integration guide
- [README.md](README.md): General service documentation
- [../image-upload-microservice/JSON_METADATA_SUPPORT.md](../image-upload-microservice/JSON_METADATA_SUPPORT.md): Upstream JSON support
- [../gedcom-generation-microservice/OPTIONAL_PAGE_NUMBER_FIX.md](../gedcom-generation-microservice/OPTIONAL_PAGE_NUMBER_FIX.md): Downstream page number handling

## Future Enhancements

1. **Metadata Caching**: Cache JSON metadata to reduce S3 calls
2. **Schema Validation**: Validate JSON structure before processing
3. **Additional Formats**: Support other metadata formats beyond Skanoteka
4. **Configurable Priority**: Allow configuration of metadata source priority
5. **Batch Processing**: Optimize for processing multiple pages from same document
