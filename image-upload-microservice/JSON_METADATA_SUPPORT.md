# JSON Metadata Support for Scraper Integration

## Overview

The image-upload-microservice now supports JSON metadata files created by the scraper. When the scraper downloads images from Skanoteka, it creates two files per image:

1. **Image file** (e.g., `301.jpg`)
2. **JSON metadata file** (e.g., `301.json`)

The microservice automatically detects and processes these JSON files, extracting the metadata and attaching it to the uploaded images.

## How It Works

### Scraper Output Format

The scraper saves metadata in JSON format alongside each image:

```json
{
  "place": "Bolechów",
  "unit": "4500 M-1874-1937-Bolechów",
  "years": "1874-1937",
  "page": "301.jpg (301 z 303)"
}
```

### Metadata Extraction

The `MetadataExtractor` service checks for companion JSON files:

- **`.json` file** - Scraped metadata from Skanoteka, no network request needed
- If no JSON file is found, no metadata is extracted

### Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    JSON Metadata Processing                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Scraper Output:                                                 │
│  ├─> unit_4500/301.jpg                                          │
│  └─> unit_4500/301.json                                         │
│                                                                   │
│  ↓                                                                │
│                                                                   │
│  Image Upload Microservice:                                      │
│  1. Detects 301.jpg                                              │
│  2. Looks for 301.json                                           │
│  3. Parses JSON metadata (no network request!)                   │
│  4. Validates image                                              │
│  5. Uploads to S3 with metadata                                  │
│  6. Sends SQS notification with metadata                         │
│  7. Handles post-upload action for both files                    │
│                                                                   │
│  ↓                                                                │
│                                                                   │
│  S3 Object Metadata:                                             │
│  ├─> skanoteka-place: "Bolechów"                               │
│  ├─> skanoteka-unit: "4500 M-1874-1937-Bolechów"              │
│  ├─> skanoteka-years: "1874-1937"                              │
│  └─> skanoteka-page: "301.jpg (301 z 303)"                     │
│                                                                   │
│  ↓                                                                │
│                                                                   │
│  SQS Message:                                                     │
│  {                                                                │
│    "s3_uri": "s3://bucket/uploads/301.jpg",                     │
│    "metadata": {                                                  │
│      "original_filename": "301.jpg",                             │
│      "skanoteka": {                                               │
│        "place": "Bolechów",                                      │
│        "unit": "4500 M-1874-1937-Bolechów",                    │
│        "years": "1874-1937",                                     │
│        "page": "301.jpg (301 z 303)"                            │
│      }                                                             │
│    }                                                               │
│  }                                                                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Post-Upload Actions

The microservice handles companion JSON files according to the configured `POST_UPLOAD_ACTION`:

### Keep (default)
```bash
POST_UPLOAD_ACTION=keep
```
- Both image and JSON files remain in the watched directory
- Useful for testing or when you want to preserve originals

### Archive
```bash
POST_UPLOAD_ACTION=archive
ARCHIVE_DIRECTORY=/app/processed-images
```
- Both image and JSON files are moved to the archive directory
- Preserves the relationship between image and metadata
- Archive structure: `YYYY/MM/DD/filename.jpg` and `YYYY/MM/DD/filename.json`

### Delete
```bash
POST_UPLOAD_ACTION=delete
```
- Both image and JSON files are deleted after successful upload
- Saves disk space
- Metadata is preserved in S3 object metadata and SQS messages

## Benefits of JSON Metadata

### 1. **No Network Requests**
- Metadata is already extracted by the scraper
- No need to fetch pages from Skanoteka
- Faster processing

### 2. **Offline Operation**
- Works even if Skanoteka is unavailable
- No dependency on external services
- More reliable

### 3. **Consistent Metadata**
- Metadata extracted once by scraper
- Same metadata used throughout pipeline
- No risk of page changes between scraping and upload

### 4. **Better Performance**
- Instant metadata parsing (JSON.parse)
- No HTTP requests or HTML parsing
- Lower latency

## Configuration

No additional configuration is required. The feature works automatically when:

1. `ENABLE_METADATA_EXTRACTION=true` (default)
2. JSON files exist alongside images
3. JSON files contain valid Skanoteka metadata fields

## Example Usage

### Scraper Setup
```bash
# Scraper saves to watched directory
cd scraper
python scraper.py
# Output: /app/watched-images/unit_4500/*.jpg and *.json
```

### Microservice Processing
```bash
# Microservice watches the same directory
cd image-upload-microservice
docker-compose up

# Logs will show:
# ✓ found_metadata_in_json_file: file=301.jpg, json_file=301.json
# ✓ skanoteka_metadata_extracted: place=Bolechów, unit=4500...
# ✓ file_uploaded: s3_uri=s3://bucket/uploads/301.jpg
# ✓ notification_sent: message_id=...
# ✓ post_upload_archived_with_json: archive_path=...
```

## Validation

The JSON metadata is validated to ensure it contains at least one expected Skanoteka field:
- `place` (Miejscowość)
- `unit` (Jednostka)
- `years` (Lata)
- `page` (Plik)

If the JSON file doesn't contain any of these fields, no metadata is extracted.

## Error Handling

### Invalid JSON
```
⚠️ failed_to_parse_json_file: json_file=301.json, error=...
```
No metadata extracted for this image.

### Missing JSON Fields
```
⚠️ json_file_missing_skanoteka_fields: json_file=301.json
```
No metadata extracted for this image.

### File Read Errors
```
⚠️ failed_to_read_json_file: json_file=301.json, error=...
```
No metadata extracted for this image.

## Statistics

The microservice tracks metadata extraction:

```json
{
  "files_processed": 150,
  "files_uploaded": 148,
  "metadata_extracted": 148,
  "validation_failures": 2
}
```

## Compatibility

### Forward Compatible
- Works with any JSON structure containing Skanoteka fields
- Additional fields in JSON are preserved
- Future scraper enhancements automatically supported

## Testing

### Test with Sample Files

1. Create test image and JSON:
```bash
# Create test directory
mkdir -p /app/watched-images/test

# Copy sample image
cp sample.jpg /app/watched-images/test/sample.jpg

# Create companion JSON
cat > /app/watched-images/test/sample.json << EOF
{
  "place": "Test Location",
  "unit": "TEST-001",
  "years": "2024",
  "page": "sample.jpg (1 z 1)"
}
EOF
```

2. Watch logs:
```bash
docker-compose logs -f image-upload-microservice
```

3. Verify S3 metadata:
```bash
aws s3api head-object \
  --bucket your-bucket \
  --key uploads/sample.jpg \
  --query Metadata
```

Expected output:
```json
{
  "skanoteka-place": "Test Location",
  "skanoteka-unit": "TEST-001",
  "skanoteka-years": "2024",
  "skanoteka-page": "sample.jpg (1 z 1)"
}
```

## Troubleshooting

### JSON files not being processed
- Check file permissions (must be readable)
- Verify JSON syntax with `jq < file.json`
- Ensure JSON contains at least one Skanoteka field
- Check logs for parsing errors

### Metadata not in S3
- Verify `ENABLE_METADATA_EXTRACTION=true`
- Check S3 object metadata (not object content)
- Ensure upload succeeded (check logs)

### JSON files not cleaned up
- Verify `POST_UPLOAD_ACTION` setting
- Check archive directory permissions
- Review post-upload action logs

## Related Documentation

- [METADATA_INTEGRATION.md](./METADATA_INTEGRATION.md) - Full metadata integration guide
- [USAGE.md](./USAGE.md) - General usage instructions
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [scraper/SKANOTEKA_ANALYSIS.md](../scraper/SKANOTEKA_ANALYSIS.md) - Scraper documentation
