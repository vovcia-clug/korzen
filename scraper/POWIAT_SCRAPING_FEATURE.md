# Powiat Scraping Feature

## Overview
Enhanced the scraper to support scraping entire powiaty (districts) from metryki.genealodzy.pl, with improved directory structure and duplicate detection.

## New Features

### 1. Powiat-Level Scraping
The scraper now supports scraping entire powiaty (districts) instead of just individual collections.

**Example URL**: `https://metryki.genealodzy.pl/pow-24`

The scraper will:
1. Extract all collections from the powiat page
2. For each collection, extract all units
3. For each unit, download all images

### 2. Improved Directory Structure
Images are now organized in a hierarchical structure:

```
/app/watched-images/
  └── {powiat_name}/
      └── {collection_id}/
          └── {unit_number}/
              ├── 000.jpg
              ├── 000.json
              ├── 001.jpg
              ├── 001.json
              └── ...
```

**Example**:
```
/app/watched-images/
  └── krakowski/
      └── 1784/
          └── 3500/
              ├── 000.jpg
              ├── 000.json
              └── ...
```

### 3. Skip Already Downloaded Files
The scraper now checks if files already exist before downloading:
- Scans the target directory for existing `.jpg` and `.jpeg` files
- Skips downloading files that already exist
- Still navigates through all pages to maintain proper sequencing
- Displays skip messages: `⏭️  Skipping {filename} - already downloaded`

## Configuration

Update the configuration at the top of [`scraper.py`](scraper.py:15):

```python
# --- CONFIGURATION ---
POWIAT_URL = "https://metryki.genealodzy.pl/pow-24"  # Powiat to scrape
BASE_URL = "https://skanoteka.genealodzy.pl"
METRYKI_BASE_URL = "https://metryki.genealodzy.pl"
DOWNLOAD_FOLDER = "/app/watched-images"
MAX_IMAGES_PER_UNIT = 1000  # Maximum images to download per unit
```

## New Functions

### `extract_collections_from_powiat(powiat_url)`
Extracts all collection links from a powiat (district) page.

**Parameters**:
- `powiat_url` (str): URL of the powiat page (e.g., `https://metryki.genealodzy.pl/pow-24`)

**Returns**:
- List of dictionaries containing:
  - `id`: Collection ID
  - `url`: Full URL to the collection
  - `name`: Collection name/description
  - `powiat`: Powiat name extracted from page

### `extract_units_from_collection(url, collection_id)`
Updated to accept collection_id parameter for better tracking.

### `scrape_unit_images(start_url, unit_info, powiat_name, collection_id)`
Updated to:
- Accept `powiat_name` and `collection_id` parameters
- Create hierarchical directory structure
- Check for already downloaded files
- Skip existing files while maintaining navigation

## Usage Examples

### Scrape a Specific Powiat
```python
POWIAT_URL = "https://metryki.genealodzy.pl/pow-24"
```

### Scrape Different Powiaty
Just change the powiat number in the URL:
- `pow-24` - Powiat 24
- `pow-25` - Powiat 25
- etc.

## Progress Tracking

The scraper now tracks and displays:
- Collections processed
- Units processed per collection
- Total images downloaded
- Progress through collections and units

**Example output**:
```
--- Progress: Collection 2/5, Unit 3/12, 450 total images ---
```

## Benefits

1. **Organized Storage**: Clear hierarchy makes it easy to find images by powiat, collection, and unit
2. **Resume Capability**: Can restart scraping without re-downloading existing files
3. **Bandwidth Savings**: Skips already downloaded files
4. **Scalability**: Can scrape entire districts with hundreds of collections
5. **Traceability**: Directory structure preserves the organizational hierarchy

## Technical Details

### Powiat Name Extraction
The powiat name is extracted from the page title using regex:
```python
match = re.search(r'Powiat\s+([^\s,]+)', title_text, re.IGNORECASE)
```

### Collection ID Extraction
Collection IDs are extracted from URLs using regex:
```python
collection_id_match = re.search(r'/id(\d+)$', href)
```

### Duplicate Detection
Files are checked before download:
```python
existing_files = {f for f in os.listdir(unit_folder) 
                  if f.endswith('.jpg') or f.endswith('.jpeg')}
if filename in existing_files:
    print(f"⏭️  Skipping {filename} - already downloaded")
```

## Migration from Old Version

If you have existing downloads in the old structure (`unit_{number}/`), you can:
1. Manually reorganize them into the new structure
2. Or simply re-run the scraper (it will skip existing files)

## Future Enhancements

Potential improvements:
- Add command-line arguments for powiat URL
- Support scraping multiple powiaty in one run
- Add resume from specific collection/unit
- Implement parallel downloading for faster scraping
- Add progress bar for visual feedback
