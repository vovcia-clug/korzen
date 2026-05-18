# Skanoteka Metadata Extraction

## Overview

This document describes the metadata extraction functionality added to the Skanoteka scraper. The extension allows extraction of genealogical record metadata from Skanoteka page URLs without requiring Selenium.

## Features

Two new functions have been added to [`scraper.py`](scraper.py):

### 1. `extract_metadata_from_url(url)`

Extracts metadata from a Skanoteka page URL using HTTP requests and BeautifulSoup.

**Parameters:**
- `url` (str): The Skanoteka page URL to extract metadata from

**Returns:**
- `dict`: Metadata in JSON format with the following keys:
  - `place` (str): Miejscowość (locality/place name)
  - `unit` (str): Jednostka (archival unit identifier)
  - `years` (str): Lata (year range covered)
  - `page` (str): Plik (page/file number with total count)
  - `error` (str, optional): Error message if extraction failed

**Example:**
```python
from scraper import extract_metadata_from_url

url = "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg"
metadata = extract_metadata_from_url(url)

print(metadata)
# Output:
# {
#   "place": "Bolechów",
#   "unit": "4500 M-1874-1937-Bolechów",
#   "years": "1874-1937",
#   "page": "301.jpg (301 z 303)"
# }
```

### 2. `extract_metadata_from_driver(driver)`

Extracts metadata from the current page loaded in a Selenium WebDriver instance. This is useful when already navigating pages with Selenium during scraping operations.

**Parameters:**
- `driver`: Selenium WebDriver instance with page already loaded

**Returns:**
- `dict`: Same format as `extract_metadata_from_url()`

**Example:**
```python
from selenium import webdriver
from scraper import extract_metadata_from_driver

driver = webdriver.Chrome()
driver.get("https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg")

metadata = extract_metadata_from_driver(driver)
print(metadata)
```

## Metadata Fields

The extracted metadata corresponds to the information displayed in the sidebar of Skanoteka viewer pages:

| Field | Polish Label | Description | Example |
|-------|--------------|-------------|---------|
| `place` | Miejscowość | Locality/place name | "Bolechów" |
| `unit` | Jednostka | Archival unit identifier | "4500 M-1874-1937-Bolechów" |
| `years` | Lata | Year range covered by the records | "1874-1937" |
| `page` | Plik | Current page/file with total count | "301.jpg (301 z 303)" |

## Technical Implementation

### HTML Structure

The metadata is extracted from the sidebar `<div>` element with class `sidebar`. The structure is:

```html
<div class="sidebar">
    ...
    <span class="bold">Miejscowość:</span><br>
    Bolechów
    <br><span class="bold">Jednostka:</span><br>
    4500 M-1874-1937-Bolechów
    <br><span class="bold">Lata:</span><br>
    1874-1937
    <br><span class="bold">Plik:</span><br>
    301.jpg (301 z 303)
</div>
```

### Extraction Method

The function uses regex patterns to extract values following the Polish labels:

```python
place_match = re.search(r'Miejscowość:\s*\n\s*([^\n]+)', sidebar_text)
unit_match = re.search(r'Jednostka:\s*\n\s*([^\n]+)', sidebar_text)
years_match = re.search(r'Lata:\s*\n\s*([^\n]+)', sidebar_text)
file_match = re.search(r'Plik:\s*\n\s*([^\n]+)', sidebar_text)
```

## Test Results

### Test URL
```
https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg&x=0&y=0&zoom=1.0
```

### Extracted Metadata
```json
{
  "place": "Bolechów",
  "unit": "4500 M-1874-1937-Bolechów",
  "years": "1874-1937",
  "page": "301.jpg (301 z 303)"
}
```

### Validation Results
- ✓ All expected fields present
- ✓ All fields have values
- ✓ No errors
- ✓ JSON format valid

## Integration with Existing Scraper

The metadata extraction functions are designed to work alongside the existing scraper functionality:

1. **Standalone Usage**: Use `extract_metadata_from_url()` for quick metadata extraction without running the full scraper
2. **Integrated Usage**: Use `extract_metadata_from_driver()` within the scraping loop to capture metadata for each page being downloaded
3. **Non-Invasive**: The existing scraper functionality remains completely intact

## Use Cases

1. **Metadata Collection**: Extract metadata for cataloging purposes without downloading images
2. **Validation**: Verify that scraped images match expected metadata
3. **Progress Tracking**: Track which records have been processed by unit and page number
4. **Database Integration**: Store metadata alongside downloaded images for searchability

## Dependencies

The metadata extraction functions require:
- `requests` - For HTTP requests
- `beautifulsoup4` - For HTML parsing
- `re` (standard library) - For regex pattern matching
- `json` (standard library) - For JSON formatting

These are already included in the scraper's existing dependencies.

## Error Handling

The functions include comprehensive error handling:

- **Network Errors**: Returns error message in the `error` field if URL cannot be fetched
- **Parsing Errors**: Returns error message if HTML structure is unexpected
- **Missing Elements**: Returns `None` for individual fields that cannot be found
- **Graceful Degradation**: Always returns a valid dictionary structure

## Future Enhancements

Potential improvements for future versions:

1. **Batch Processing**: Add function to extract metadata from multiple URLs
2. **CSV Export**: Export metadata to CSV format for spreadsheet analysis
3. **Database Storage**: Direct integration with database for metadata storage
4. **Validation Rules**: Add validation for expected metadata formats
5. **Language Support**: Support for extracting metadata from other language versions
