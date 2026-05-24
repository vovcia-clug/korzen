# Powiat ID Collision Fix

## Problem Summary

When scanning a powiat (district) with multiple collections, units with the same ID numbers across different collections were being treated as the same document, causing:

- **Mixed Pages**: Pages from different collections grouped together
- **Missing Pages**: Each document appeared incomplete
- **Timeouts**: Documents timed out waiting for pages that would never arrive
- **Invalid GEDCOM**: Generated files contained mixed data from different sources
- **Data Corruption**: Records from different time periods/locations got merged

### Example

```
Powiat: krakowski
├── Collection 1784
│   └── Unit 3500 (150 pages)
└── Collection 1885
    └── Unit 3500 (175 pages)
```

Both units were assigned `document_id = "3500"`, causing collision in the document grouper.

## Solution

Generate **composite document IDs** that include both collection and unit identifiers:
- `document_id = "1784-3500"` (instead of just `"3500"`)
- `document_id = "1885-3500"` (instead of just `"3500"`)

## Changes Made

### 1. OCR Metadata Extractor ([`ocr-image-microservice/src/services/metadata_extractor.py`](ocr-image-microservice/src/services/metadata_extractor.py))

**Updated `extract_from_s3_path()` method** to detect powiat/collection/unit structure and generate composite document IDs:

```python
# For path: s3://bucket/uploads/krakowski/1784/3500/001.jpg
# Extracts:
#   - collection_id = "1784"
#   - unit_number = "3500"
#   - document_id = "1784-3500"

if len(parts) >= 3:
    potential_collection = parts[-3]
    potential_unit = parts[-2]
    
    if potential_collection.isdigit() and potential_unit.isdigit():
        collection_id = potential_collection
        unit_number = potential_unit
        document_id = f"{collection_id}-{unit_number}"
        
        metadata['collection_id'] = collection_id
        metadata['unit_number'] = unit_number
        metadata['document_id'] = document_id
```

### 2. OCR JSON Metadata Loader ([`ocr-image-microservice/src/services/metadata_json_loader.py`](ocr-image-microservice/src/services/metadata_json_loader.py))

**Updated `extract_skanoteka_metadata()` and `_extract_document_id_from_unit()` methods**:

- Added `collection_id` parameter to `_extract_document_id_from_unit()`
- Creates composite document_id when collection_id is available
- Added new `_extract_unit_number()` helper method
- Extracts and stores `collection_id`, `unit_number`, and `powiat` separately

```python
def _extract_document_id_from_unit(self, unit: str, collection_id: Optional[str] = None) -> Optional[str]:
    match = re.match(r'^(\d+)', unit.strip())
    if match:
        unit_number = match.group(1)
        
        if collection_id:
            document_id = f"{collection_id}-{unit_number}"
        else:
            document_id = unit_number
        
        return document_id
```

### 3. Forward OCR Results Script ([`ocr-image-microservice/forward_ocr_results.py`](ocr-image-microservice/forward_ocr_results.py))

**Updated `extract_metadata_from_path()` method** to generate composite document IDs:

```python
# For path: ocr-results/powiat/collection_id/unit_number/page.md
if len(parent_parts) >= 2:
    potential_collection = parent_parts[-2]
    potential_unit = parent_parts[-1]
    
    if potential_collection.isdigit() and potential_unit.isdigit():
        metadata["document_id"] = f"{potential_collection}-{potential_unit}"
        metadata["collection_id"] = potential_collection
        metadata["unit_number"] = potential_unit
```

### 4. Scraper ([`scraper/scraper.py`](scraper/scraper.py))

**Updated metadata extraction** to include `collection_id` and `powiat` in JSON files:

```python
# Extract metadata from current page
metadata = extract_metadata_from_driver(driver)

# Add collection_id and powiat to metadata for composite document IDs
metadata['collection_id'] = collection_id
metadata['powiat'] = powiat_name
```

### 5. OCR Main Processing ([`ocr-image-microservice/src/main.py`](ocr-image-microservice/src/main.py))

**Updated metadata merging** to include collection context fields:

```python
if skanoteka_metadata:
    if 'document_id' in skanoteka_metadata:
        metadata['document_id'] = skanoteka_metadata['document_id']
    
    if 'collection_id' in skanoteka_metadata:
        metadata['collection_id'] = skanoteka_metadata['collection_id']
    
    if 'unit_number' in skanoteka_metadata:
        metadata['unit_number'] = skanoteka_metadata['unit_number']
    
    if 'powiat' in skanoteka_metadata:
        metadata['powiat'] = skanoteka_metadata['powiat']
```

## Data Flow

### Before Fix

```
Scraper → S3: krakowski/1784/3500/001.jpg
         ↓
OCR Microservice: document_id = "3500"
         ↓
GEDCOM Microservice: Groups as document "3500"

Scraper → S3: krakowski/1885/3500/001.jpg
         ↓
OCR Microservice: document_id = "3500"  ❌ COLLISION!
         ↓
GEDCOM Microservice: Groups as document "3500"  ❌ MIXED!
```

### After Fix

```
Scraper → S3: krakowski/1784/3500/001.jpg + metadata.json (collection_id: "1784")
         ↓
OCR Microservice: document_id = "1784-3500"
         ↓
GEDCOM Microservice: Groups as document "1784-3500" ✅

Scraper → S3: krakowski/1885/3500/001.jpg + metadata.json (collection_id: "1885")
         ↓
OCR Microservice: document_id = "1885-3500"
         ↓
GEDCOM Microservice: Groups as document "1885-3500" ✅ SEPARATE!
```

## Verification Steps

After deploying the fix:

1. **Check OCR messages** have unique `document_id` values:
   ```
   document_id: "1784-3500" (not just "3500")
   document_id: "1885-3500" (not just "3500")
   ```

2. **Verify document grouper** sees separate documents:
   ```
   Document 1784-3500: 150 pages
   Document 1885-3500: 175 pages
   ```

3. **Confirm no more**:
   - Mixed pages warnings
   - Timeout issues for documents with many missing pages
   - Invalid GEDCOM files with mixed data

4. **Check logs** for composite document IDs:
   ```
   INFO - Extracted composite document_id=1784-3500 (collection=1784, unit=3500) from path
   INFO - Using document_id from Skanoteka: 1784-3500
   ```

## Backward Compatibility

The fix maintains backward compatibility:

- **Single collection scanning**: Still works (uses unit number as document_id)
- **Non-powiat structures**: Unaffected (uses existing logic)
- **Existing data**: Can be reprocessed with new logic

## Testing

To test the fix:

1. **Scrape a powiat** with multiple collections containing units with same numbers
2. **Monitor OCR logs** for composite document IDs
3. **Check GEDCOM generation** for separate document processing
4. **Verify GEDCOM files** contain data from single collection only

## Related Files

- [`ocr-image-microservice/src/services/metadata_extractor.py`](ocr-image-microservice/src/services/metadata_extractor.py)
- [`ocr-image-microservice/src/services/metadata_json_loader.py`](ocr-image-microservice/src/services/metadata_json_loader.py)
- [`ocr-image-microservice/forward_ocr_results.py`](ocr-image-microservice/forward_ocr_results.py)
- [`ocr-image-microservice/src/main.py`](ocr-image-microservice/src/main.py)
- [`scraper/scraper.py`](scraper/scraper.py)
- [`gedcom-generation-microservice/src/services/document_grouper.py`](gedcom-generation-microservice/src/services/document_grouper.py)

## Impact

- ✅ **Prevents ID collisions** across collections
- ✅ **Ensures data integrity** in GEDCOM generation
- ✅ **Eliminates timeouts** caused by mixed pages
- ✅ **Maintains traceability** with collection and unit context
- ✅ **Backward compatible** with existing workflows
