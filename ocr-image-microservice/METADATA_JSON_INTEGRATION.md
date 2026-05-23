# JSON Metadata Integration

## Overview

The OCR Image Microservice now supports loading and processing companion JSON metadata files that are uploaded alongside images. This feature enables automatic extraction of Skanoteka metadata including document IDs and page numbers for proper document grouping.

## Features

### 1. JSON Metadata Loading

The service automatically looks for companion `.json` files in S3 for each image being processed:

- **Image**: `s3://bucket/uploads/unit_4500/301.jpg`
- **JSON**: `s3://bucket/uploads/unit_4500/301.json`

### 2. Skanoteka Metadata Extraction

When JSON metadata is found, the service extracts Skanoteka-specific fields:

```json
{
  "place": "Bolechów",
  "unit": "4500 M-1874-1937-Bolechów",
  "years": "1874-1937",
  "page": "301.jpg (301 z 303)"
}
```

**Extracted Fields:**
- `document_id`: Extracted from unit number (e.g., "4500")
- `page_number`: Extracted from page field (e.g., 301)
- `total_pages`: Extracted from page field (e.g., 303)
- `place`: Location name
- `unit`: Full unit description
- `years`: Date range

### 3. Directory Structure Preservation

OCR results are uploaded to S3 preserving the original directory structure:

**Input:**
```
s3://bucket/uploads/unit_4500/301.jpg
```

**Output:**
```
s3://bucket/ocr-results/unit_4500/301.md
```

This ensures that documents remain organized by their source structure.

## Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    OCR Processing with JSON Metadata             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Step 1: Download image from S3                                  │
│  ├─> s3://bucket/uploads/unit_4500/301.jpg                      │
│                                                                   │
│  Step 2: Load JSON metadata (if available)                       │
│  ├─> s3://bucket/uploads/unit_4500/301.json                     │
│  └─> Parse Skanoteka fields                                      │
│                                                                   │
│  Step 3: Extract metadata from S3 path and tags                  │
│  ├─> Extract from S3 URI structure                              │
│  └─> Get S3 object tags                                          │
│                                                                   │
│  Step 4: Process Skanoteka metadata                              │
│  ├─> Extract document_id from unit (e.g., "4500")              │
│  ├─> Extract page_number from page field (e.g., 301)           │
│  ├─> Extract total_pages from page field (e.g., 303)           │
│  └─> Merge with existing metadata (Skanoteka takes precedence)  │
│                                                                   │
│  Step 5: Perform OCR                                             │
│  └─> Process image with Datalab SDK                             │
│                                                                   │
│  Step 6: Upload OCR result to S3                                 │
│  ├─> Preserve directory structure                               │
│  └─> s3://bucket/ocr-results/unit_4500/301.md                  │
│                                                                   │
│  Step 7: Publish to SQS                                          │
│  └─> Include all metadata (including Skanoteka)                 │
│                                                                   │
│  Step 8: Delete message from input queue                         │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Metadata Priority

When multiple sources provide the same metadata field, the priority is:

1. **Skanoteka JSON metadata** (highest priority)
2. **S3 object tags**
3. **S3 URI path extraction** (lowest priority)

This ensures that explicitly provided Skanoteka metadata always takes precedence.

## Example Metadata Output

### Input JSON
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
    "document_id": "4500",
    "page_number": 301,
    "total_pages": 303,
    "skanoteka": {
        "place": "Bolechów",
        "unit": "4500 M-1874-1937-Bolechów",
        "years": "1874-1937",
        "page": "301.jpg (301 z 303)",
        "document_id": "4500",
        "page_number": 301,
        "total_pages": 303
    },
    "image_width": 3000,
    "image_height": 4000,
    "filename": "301.jpg"
}
```

### Published SQS Message
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
    },
    "image_width": 3000,
    "image_height": 4000
  }
}
```

## Page Number Calculation

The service extracts page numbers from the Skanoteka page field using pattern matching:

### Pattern: "filename (X z Y)"
- **X**: Current page number
- **Y**: Total pages

### Examples:
- `"301.jpg (301 z 303)"` → page_number=301, total_pages=303
- `"005.jpg (5 z 175)"` → page_number=5, total_pages=175
- `"042.jpg (42 z 100)"` → page_number=42, total_pages=100

### Fallback:
If the pattern doesn't match, the service attempts to extract the page number from the filename itself.

## Document Grouping

The extracted `document_id` and `page_number` enable proper document grouping in the downstream GEDCOM generation service:

1. **Document ID**: Groups all pages belonging to the same document/unit
2. **Page Number**: Orders pages within each document
3. **Total Pages**: Determines when all pages have been received

## Benefits

### 1. Accurate Document Grouping
- Skanoteka unit numbers provide reliable document IDs
- Page numbers ensure correct ordering
- Total pages enable completion detection

### 2. Preserved Context
- Full Skanoteka metadata is preserved in messages
- Location, date range, and unit information available downstream
- Enables better GEDCOM generation with contextual information

### 3. Organized Storage
- Directory structure preservation maintains organization
- Easy to locate related files
- Supports batch processing by directory

### 4. Backward Compatible
- Works with or without JSON metadata
- Falls back to S3 path/tag extraction if JSON not available
- No breaking changes to existing functionality

## Error Handling

### JSON File Not Found
```
INFO: No JSON metadata file found for: s3://bucket/uploads/image.jpg
INFO: Using extracted metadata only
```
Processing continues with metadata extracted from S3 path and tags.

### JSON Parse Error
```
WARNING: Failed to load JSON metadata for s3://bucket/uploads/image.jpg: Invalid JSON
```
Processing continues with fallback metadata extraction.

### Missing Skanoteka Fields
```
DEBUG: JSON data does not contain Skanoteka fields
```
JSON is ignored, fallback metadata extraction used.

## Configuration

No additional configuration is required. The feature works automatically when:

1. JSON files exist in S3 alongside images
2. JSON files contain valid Skanoteka metadata fields
3. Image upload microservice has uploaded both image and JSON

## Testing

### Test with Sample Data

1. **Upload test files to S3:**
```bash
# Upload image
aws s3 cp test.jpg s3://bucket/uploads/unit_test/001.jpg

# Upload companion JSON
cat > 001.json << EOF
{
  "place": "Test Location",
  "unit": "9999 TEST-2024",
  "years": "2024",
  "page": "001.jpg (1 z 10)"
}
EOF
aws s3 cp 001.json s3://bucket/uploads/unit_test/001.json
```

2. **Send SQS message:**
```json
{
  "s3_uri": "s3://bucket/uploads/unit_test/001.jpg"
}
```

3. **Verify output:**
```bash
# Check OCR result location
aws s3 ls s3://bucket/ocr-results/unit_test/

# Check SQS output message
aws sqs receive-message --queue-url <output-queue-url>
```

## Related Services

### Image Upload Microservice
Uploads both image and JSON files to S3 in the same directory structure.

### GEDCOM Generation Microservice
Consumes OCR results and uses `document_id`, `page_number`, and `total_pages` for document grouping.

## Implementation Details

### New Components

1. **[`metadata_json_loader.py`](src/services/metadata_json_loader.py)**
   - Loads JSON files from S3
   - Parses Skanoteka metadata
   - Extracts document_id and page numbers

2. **[`s3_handler.py`](src/services/s3_handler.py)** (updated)
   - Added `download_json()` method
   - Added `preserve_structure` parameter to `upload_result()`

3. **[`main.py`](src/main.py)** (updated)
   - Integrated JSON metadata loading
   - Added Skanoteka metadata processing
   - Updated processing flow

## Troubleshooting

### JSON files not being loaded
- Verify JSON files exist in S3 at expected location
- Check S3 permissions for reading JSON files
- Review logs for download errors

### Page numbers not extracted
- Verify JSON contains `page` field
- Check page field format matches pattern: "filename (X z Y)"
- Review logs for extraction warnings

### Directory structure not preserved
- Verify `preserve_structure=True` in upload_result call
- Check output S3 keys in logs
- Ensure original S3 URI contains directory structure

## Future Enhancements

- Support for additional metadata formats
- Configurable metadata priority rules
- Metadata validation and schema enforcement
- Caching of JSON metadata to reduce S3 calls
