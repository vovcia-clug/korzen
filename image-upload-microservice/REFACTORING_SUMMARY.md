# Metadata Handling Refactoring Summary

## Overview
Refactored the image upload microservice to **stop processing metadata** and instead **only upload JSON files alongside image files** to S3.

## Changes Made

### 1. **metadata_extractor.py** → **Simplified to MetadataHandler**
- **Removed**: All metadata extraction and processing logic
  - `extract_metadata_from_url()` - Scraped Skanoteka URLs
  - `is_skanoteka_url()` - URL validation
  - Web scraping with BeautifulSoup
  - Regex parsing of metadata fields
- **Kept**: Simple companion JSON file detection
  - `find_companion_json()` - Locates JSON files alongside images
- **Renamed**: `MetadataExtractor` → `MetadataHandler`

### 2. **upload_orchestrator.py** → **Added JSON Upload Logic**
- **Removed**: 
  - `enable_metadata_extraction` parameter
  - Metadata extraction workflow
  - Skanoteka metadata processing
- **Added**:
  - JSON file upload alongside image files
  - `json_files_uploaded` statistic
  - JSON S3 URI added to notification metadata
- **Updated**: Statistics tracking (removed `metadata_extracted`, added `json_files_uploaded`)

### 3. **s3_uploader.py** → **Added JSON Upload Method**
- **Added**: `upload_json_file()` method
  - Uploads JSON files to same S3 location as images
  - Uses same key structure with `.json` extension
  - Includes metadata linking JSON to image
  - Proper content-type (`application/json`)
- **Removed**: Skanoteka metadata fields from `_prepare_metadata()`
- **Added**: `json-metadata-uri` field to image metadata

### 4. **config.py** → **Removed Configuration**
- **Removed**: `enable_metadata_extraction` field
- **Removed**: `ENABLE_METADATA_EXTRACTION` environment variable

### 5. **main.py** → **Simplified Initialization**
- **Removed**: `enable_metadata_extraction` parameter from orchestrator initialization

### 6. **requirements.txt** → **Removed Dependencies**
- **Removed**: `requests>=2.31.0` (HTTP requests for metadata extraction)
- **Removed**: `beautifulsoup4>=4.12.0` (HTML parsing for metadata extraction)

## New Workflow

### Before (Old Workflow)
1. Detect image file
2. Validate image
3. **Extract metadata from Skanoteka URL** ❌
4. **Parse and process metadata** ❌
5. Upload image to S3 with processed metadata
6. Send SQS notification
7. Post-upload action

### After (New Workflow)
1. Detect image file
2. Validate image
3. Upload image to S3
4. **Check for companion JSON file** ✅
5. **Upload JSON file to S3 (if exists)** ✅
6. Send SQS notification (includes JSON S3 URI)
7. Post-upload action

## Benefits

1. **Separation of Concerns**: Upload service no longer processes metadata
2. **Simpler Logic**: Removed complex web scraping and parsing
3. **Fewer Dependencies**: Removed `requests` and `beautifulsoup4`
4. **Better Performance**: No HTTP requests or HTML parsing
5. **More Flexible**: JSON files can contain any metadata structure
6. **Downstream Processing**: Other services can process metadata as needed

## S3 Structure

For each uploaded image, the service now creates:

```
s3://bucket/uploads/
  ├── {uuid}.jpg          # Original image
  └── {uuid}.json         # Companion metadata (if exists)
```

## Metadata Flow

- **JSON files** are uploaded as-is without processing
- **Image metadata** includes reference to JSON file location
- **SQS notifications** include `json_metadata_s3_uri` field
- **Downstream services** can fetch and process JSON as needed

## Testing

All Python files compile successfully without syntax errors:
- ✅ `src/services/metadata_extractor.py`
- ✅ `src/services/upload_orchestrator.py`
- ✅ `src/services/s3_uploader.py`
- ✅ `src/config.py`
- ✅ `src/main.py`

## Migration Notes

- Existing deployments should remove `ENABLE_METADATA_EXTRACTION` from environment variables
- JSON files should be placed alongside images with same name (e.g., `image.jpg` + `image.json`)
- Downstream services should be updated to fetch JSON from S3 if needed
