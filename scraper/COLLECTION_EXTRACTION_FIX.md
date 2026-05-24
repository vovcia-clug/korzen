# Collection Extraction Fix

## Problem

The scraper was finding 0 collections when scraping powiat pages from `https://metryki.genealodzy.pl/pow-24`. The output showed:

```
Found 0 collections in powiat 'unknown'
⚠️  No collections found in powiat!
```

## Root Cause Analysis

### Issue 1: Incorrect Collection Link Pattern

The original code in [`extract_collections_from_powiat()`](scraper.py:231) was looking for collection links with the pattern:

```python
collection_links = soup.find_all('a', href=re.compile(r'/id\d+$'))
```

This pattern expected links starting with `/id` (e.g., `/id1883`), but the actual HTML structure uses relative paths without the leading slash:

```html
<a class="asc" href="id1883">325</a>
<a class="asc" href="id2039">2175</a>
```

### Issue 2: Incorrect Powiat Identifier Extraction

The code was trying to extract the powiat name from the page title, which is generic and doesn't contain useful information. This resulted in "unknown" being used as the directory name.

The powiat identifier should be extracted directly from the URL (e.g., `https://metryki.genealodzy.pl/pow-24` → `pow-24`).

## Solution

### Fix 1: Updated Collection Link Pattern

Changed the regex pattern to match relative paths starting with `id`:

```python
# OLD: collection_links = soup.find_all('a', href=re.compile(r'/id\d+$'))
# NEW:
collection_links = soup.find_all('a', href=re.compile(r'^id\d+$'))
```

Also updated the extraction logic:

```python
# Extract collection ID from href
collection_id_match = re.search(r'^id(\d+)$', href)
if not collection_id_match:
    continue

collection_id = collection_id_match.group(1)
# Build full URL: https://metryki.genealodzy.pl/id1883
collection_url = METRYKI_BASE_URL + '/' + href
```

### Fix 2: Updated Powiat Identifier Extraction

Changed to extract directly from the URL:

```python
# Extract powiat identifier from URL (e.g., pow-24)
powiat_name = "unknown"
url_match = re.search(r'(pow-\d+)', powiat_url)
if url_match:
    powiat_name = url_match.group(1)
    print(f"DEBUG: Extracted powiat identifier from URL: '{powiat_name}'")
else:
    print(f"⚠️  Could not extract powiat identifier from URL: {powiat_url}")
```

## Results

After the fix, the scraper now correctly:

1. **Finds 30 collections** from the powiat page (previously 0)
2. **Extracts powiat identifier as "pow-24"** from the URL (previously "unknown")
3. **Creates proper directory structure**: `/app/watched-images/pow-24/1883/3500/` instead of `/app/watched-images/unknown/1883/3500/`

### Example Output

```
=== EXTRACTING COLLECTIONS FROM POWIAT ===
Powiat URL: https://metryki.genealodzy.pl/pow-24
DEBUG: Extracted powiat identifier from URL: 'pow-24'
Found 30 collections in powiat 'pow-24'
  1. Collection 1883: 325
  2. Collection 2039: 2175
  3. Collection 3330: 1343
  ...
  30. Collection 1848: 3822

################################################################################
# PROCESSING COLLECTION 1/30
# Collection ID: 1883 - 325
# Powiat: pow-24
################################################################################
```

## Testing

Created test scripts to verify the fixes:

1. **[`debug_powiat_page.py`](debug_powiat_page.py)** - Analyzes the HTML structure and saves it for inspection
2. **[`test_powiat_extraction.py`](test_powiat_extraction.py)** - Tests both powiat name and collection extraction

Run tests with:

```bash
cd scraper
python test_powiat_extraction.py
```

## Files Modified

- [`scraper.py`](scraper.py) - Lines 248-275 (powiat name extraction) and lines 260-275 (collection link pattern)

## Impact

- ✅ Scraper now successfully finds and processes all collections from powiat pages
- ✅ Proper directory structure with meaningful powiat names
- ✅ No more "unknown" directories
- ✅ All 30 collections from pow-24 (Kraków) are now accessible
