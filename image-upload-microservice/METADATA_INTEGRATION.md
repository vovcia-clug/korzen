# Skanoteka Metadata Integration

## Overview

This document describes the integration of Skanoteka metadata extraction functionality into the image-upload-microservice. The integration enables automatic extraction and attachment of genealogical archive metadata when uploading images from Skanoteka sources.

## What is Skanoteka?

Skanoteka (https://skanoteka.genealodzy.pl) is a Polish genealogical archive containing digitized church records, civil registry documents, and other historical records. Each scanned image page has associated metadata including:

- **Place** (Miejscowość): The location/town where the record originates
- **Unit** (Jednostka): The archival unit identifier and description
- **Years** (Lata): The time period covered by the records
- **Page** (Plik): The specific page/file number within the unit

## Integration Architecture

### Components Added

1. **MetadataExtractor Service** (`src/services/metadata_extractor.py`)
   - Extracts metadata from Skanoteka URLs
   - Supports companion metadata files (.txt, .url)
   - Validates Skanoteka URLs
   - Handles extraction errors gracefully

2. **Modified UploadOrchestrator** (`src/services/upload_orchestrator.py`)
   - Integrates metadata extraction into upload workflow
   - Adds metadata extraction statistics
   - Configurable via `enable_metadata_extraction` parameter

3. **Enhanced S3Uploader** (`src/services/s3_uploader.py`)
   - Stores Skanoteka metadata as S3 object metadata
   - Metadata keys: `skanoteka-place`, `skanoteka-unit`, `skanoteka-years`, `skanoteka-page`, `skanoteka-source-url`

4. **Enhanced SQSNotifier** (`src/services/sqs_notifier.py`)
   - Includes Skanoteka metadata in SQS message payload
   - Downstream services (OCR microservice) receive metadata automatically

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Metadata Integration Flow                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. Image File Detected                                              │
│     └─> image.jpg                                                    │
│         └─> image.txt (companion file with Skanoteka URL)           │
│                                                                       │
│  2. MetadataExtractor                                                │
│     ├─> Read companion file                                          │
│     ├─> Extract Skanoteka URL                                        │
│     ├─> Fetch page from Skanoteka                                    │
│     ├─> Parse sidebar metadata                                       │
│     └─> Return: {place, unit, years, page, source_url}             │
│                                                                       │
│  3. UploadOrchestrator                                               │
│     ├─> Validate image                                               │
│     ├─> Extract metadata (if enabled)                                │
│     ├─> Merge metadata into upload metadata                          │
│     └─> Continue with upload workflow                                │
│                                                                       │
│  4. S3Uploader                                                        │
│     ├─> Upload image to S3                                           │
│     └─> Attach metadata as S3 object metadata:                       │
│         ├─> skanoteka-place: "Bolechów"                             │
│         ├─> skanoteka-unit: "4500 M-1874-1937-Bolechów"            │
│         ├─> skanoteka-years: "1874-1937"                            │
│         ├─> skanoteka-page: "301.jpg (301 z 303)"                   │
│         └─> skanoteka-source-url: "https://..."                     │
│                                                                       │
│  5. SQSNotifier                                                       │
│     └─> Send message with metadata:                                  │
│         {                                                             │
│           "s3_uri": "s3://bucket/key",                               │
│           "metadata": {                                               │
│             "original_filename": "image.jpg",                         │
│             "skanoteka": {                                            │
│               "place": "Bolechów",                                    │
│               "unit": "4500 M-1874-1937-Bolechów",                  │
│               "years": "1874-1937",                                   │
│               "page": "301.jpg (301 z 303)",                         │
│               "source_url": "https://..."                            │
│             }                                                          │
│           }                                                            │
│         }                                                              │
│                                                                       │
│  6. OCR Microservice (Downstream)                                    │
│     └─> Receives message with Skanoteka metadata                     │
│         └─> Can use metadata for context-aware processing            │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

No new environment variables are required. The metadata extraction is enabled by default.

To disable metadata extraction programmatically:

```python
orchestrator = UploadOrchestrator(
    image_detector=detector,
    s3_uploader=uploader,
    sqs_notifier=notifier,
    enable_metadata_extraction=False  # Disable metadata extraction
)
```

### Dependencies

Added to `requirements.txt`:

```
# HTTP requests for metadata extraction
requests>=2.31.0

# HTML parsing for metadata extraction
beautifulsoup4>=4.12.0
```

## Usage

### Method 1: Companion Metadata Files

The most common usage pattern is to place a companion `.txt` file alongside each image containing the Skanoteka URL:

```
watched-images/
├── scan_001.jpg
├── scan_001.txt          # Contains: https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&...
├── scan_002.jpg
└── scan_002.txt
```

**Example companion file content:**
```
https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg
```

### Method 2: Windows URL Shortcut Files

Alternatively, use `.url` files (Windows URL shortcut format):

```
watched-images/
├── scan_001.jpg
└── scan_001.url
```

**Example .url file content:**
```
[InternetShortcut]
URL=https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg
```

### Method 3: Direct URL Extraction (Future Enhancement)

Future versions may support extracting URLs from:
- EXIF metadata
- XMP metadata
- IPTC metadata
- Custom metadata fields

## Metadata Format

### Extracted Metadata Structure

```json
{
  "place": "Bolechów",
  "unit": "4500 M-1874-1937-Bolechów",
  "years": "1874-1937",
  "page": "301.jpg (301 z 303)",
  "source_url": "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg"
}
```

### S3 Object Metadata

Stored as S3 object metadata (HTTP headers):

```
x-amz-meta-skanoteka-place: Bolechów
x-amz-meta-skanoteka-unit: 4500 M-1874-1937-Bolechów
x-amz-meta-skanoteka-years: 1874-1937
x-amz-meta-skanoteka-page: 301.jpg (301 z 303)
x-amz-meta-skanoteka-source-url: https://skanoteka.genealodzy.pl/...
```

### SQS Message Payload

Included in the `metadata.skanoteka` field:

```json
{
  "s3_uri": "s3://my-bucket/uploads/2026/05/18/uuid.jpg",
  "metadata": {
    "original_filename": "scan_001.jpg",
    "upload_timestamp": "2026-05-18T08:00:00.000Z",
    "file_size_bytes": 2457600,
    "content_type": "image/jpeg",
    "skanoteka": {
      "place": "Bolechów",
      "unit": "4500 M-1874-1937-Bolechów",
      "years": "1874-1937",
      "page": "301.jpg (301 z 303)",
      "source_url": "https://skanoteka.genealodzy.pl/..."
    }
  },
  "source_service": "image-upload-microservice",
  "message_version": "1.0"
}
```

## Error Handling

The metadata extraction is designed to be non-blocking:

1. **No companion file**: Upload proceeds without metadata
2. **Invalid URL**: Upload proceeds without metadata
3. **Network error**: Upload proceeds without metadata (error logged)
4. **Parsing error**: Upload proceeds without metadata (error logged)

All errors are logged with appropriate context for debugging.

## Logging

### Log Events

- `metadata_extractor_initialized`: Service initialized
- `extracting_metadata_from_url`: Starting extraction
- `metadata_extracted_successfully`: Extraction succeeded
- `metadata_extraction_failed`: Extraction failed
- `found_url_in_companion_file`: Companion file found
- `no_companion_metadata_file_found`: No companion file
- `skanoteka_metadata_extracted`: Metadata added to upload

### Example Log Output

```json
{
  "timestamp": "2026-05-18T08:00:00.123Z",
  "level": "INFO",
  "event": "skanoteka_metadata_extracted",
  "file": "/app/watched-images/scan_001.jpg",
  "place": "Bolechów",
  "unit": "4500 M-1874-1937-Bolechów",
  "years": "1874-1937"
}
```

## Statistics

The upload orchestrator tracks metadata extraction statistics:

```python
stats = orchestrator.get_statistics()
# {
#   "files_processed": 100,
#   "files_uploaded": 98,
#   "files_failed": 2,
#   "metadata_extracted": 95,  # New statistic
#   ...
# }
```

## Integration with OCR Microservice

The OCR microservice automatically receives Skanoteka metadata in SQS messages. This enables:

1. **Context-aware OCR**: Use place/year information to improve recognition
2. **Automatic tagging**: Tag extracted records with source metadata
3. **Provenance tracking**: Maintain link to original source
4. **Batch processing**: Group records by unit/place for efficient processing

### Example OCR Microservice Usage

```python
# In OCR microservice message processor
message = json.loads(sqs_message.body)
skanoteka_metadata = message.get("metadata", {}).get("skanoteka")

if skanoteka_metadata:
    place = skanoteka_metadata.get("place")
    years = skanoteka_metadata.get("years")
    source_url = skanoteka_metadata.get("source_url")
    
    # Use metadata for context-aware processing
    logger.info(f"Processing record from {place}, years {years}")
    
    # Include in extracted GEDCOM
    gedcom_record.add_source_citation(source_url)
```

## Testing

### Manual Testing

1. **Create test image with companion file:**
   ```bash
   cd image-upload-microservice/watched-images
   
   # Create test image
   cp /path/to/test-image.jpg scan_test.jpg
   
   # Create companion file with Skanoteka URL
   echo "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg" > scan_test.txt
   ```

2. **Monitor logs:**
   ```bash
   docker-compose logs -f image-upload-microservice | grep skanoteka
   ```

3. **Verify S3 metadata:**
   ```bash
   aws s3api head-object \
     --bucket your-bucket \
     --key uploads/2026/05/18/uuid.jpg \
     | jq '.Metadata'
   ```

4. **Verify SQS message:**
   ```bash
   aws sqs receive-message \
     --queue-url your-queue-url \
     | jq '.Messages[0].Body | fromjson | .metadata.skanoteka'
   ```

### Unit Testing

```python
# Example unit test
from pathlib import Path
from services.metadata_extractor import MetadataExtractor

def test_metadata_extraction():
    extractor = MetadataExtractor()
    
    # Test URL validation
    assert extractor.is_skanoteka_url("https://skanoteka.genealodzy.pl/...")
    assert not extractor.is_skanoteka_url("https://example.com")
    
    # Test metadata extraction
    url = "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&..."
    metadata = extractor.extract_metadata_from_url(url)
    
    assert metadata["place"] is not None
    assert metadata["unit"] is not None
    assert metadata["source_url"] == url
```

## Performance Considerations

### Network Requests

Each metadata extraction makes one HTTP request to Skanoteka:
- **Timeout**: 30 seconds (configurable)
- **Retry**: No automatic retry (fails gracefully)
- **Impact**: Adds ~1-3 seconds per image upload

### Optimization Strategies

1. **Caching**: Future enhancement to cache metadata by URL
2. **Batch processing**: Extract metadata for multiple files in parallel
3. **Async processing**: Use async/await for non-blocking extraction
4. **Local metadata**: Store metadata locally to avoid repeated requests

## Troubleshooting

### Issue: Metadata not extracted

**Symptoms**: Images upload successfully but no Skanoteka metadata

**Solutions**:
1. Check companion file exists: `ls -la watched-images/*.txt`
2. Verify URL format in companion file
3. Check logs for extraction errors: `grep "metadata_extraction" logs/`
4. Verify network connectivity to skanoteka.genealodzy.pl
5. Check metadata extraction is enabled (default: enabled)

### Issue: Extraction timeout

**Symptoms**: Slow uploads, timeout errors in logs

**Solutions**:
1. Check network connectivity
2. Increase timeout in MetadataExtractor initialization
3. Consider disabling metadata extraction temporarily
4. Check Skanoteka website availability

### Issue: Invalid metadata format

**Symptoms**: Metadata extracted but values are None

**Solutions**:
1. Verify Skanoteka page structure hasn't changed
2. Check URL points to a valid page (not index/collection)
3. Review extraction regex patterns in metadata_extractor.py
4. Test URL manually in browser

## Future Enhancements

### Planned Features

1. **Metadata caching**: Cache extracted metadata to avoid repeated requests
2. **Bulk extraction**: Extract metadata for multiple files in parallel
3. **EXIF integration**: Store metadata in image EXIF fields
4. **Retry logic**: Automatic retry for failed extractions
5. **Metadata validation**: Validate extracted metadata format
6. **Custom extractors**: Support for other genealogical archives
7. **Metadata enrichment**: Add additional context from external sources

### API Extensions

Future versions may expose metadata extraction as a standalone API:

```python
# Standalone metadata extraction
from services.metadata_extractor import MetadataExtractor

extractor = MetadataExtractor()
metadata = extractor.extract_metadata_from_url(url)
```

## Related Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Overall microservice architecture
- **[README.md](README.md)**: General usage and setup
- **[USAGE.md](USAGE.md)**: Detailed usage examples
- **[scraper/METADATA_EXTRACTION_README.md](../scraper/METADATA_EXTRACTION_README.md)**: Original metadata extraction implementation

## Version History

### Version 1.1.0 (2026-05-18)

- ✅ Added MetadataExtractor service
- ✅ Integrated metadata extraction into upload workflow
- ✅ Enhanced S3 object metadata with Skanoteka fields
- ✅ Enhanced SQS messages with Skanoteka metadata
- ✅ Added companion file support (.txt, .url)
- ✅ Added metadata extraction statistics
- ✅ Added comprehensive logging
- ✅ Added error handling and graceful degradation

## Support

For issues, questions, or feature requests related to metadata integration:

1. Check this documentation
2. Review logs for error messages
3. Test with sample Skanoteka URLs
4. Create an issue in the repository

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-18  
**Author**: Integration Team  
**Status**: Production Ready
