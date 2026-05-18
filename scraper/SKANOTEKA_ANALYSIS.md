# Skanoteka.genealodzy.pl Page Structure Analysis

## URL Structure

The new site has a **3-level hierarchy**:

### 1. Collection Index (zespół)
**URL**: `https://skanoteka.genealodzy.pl/id5362`
- Shows collection metadata: "Księgi metrykalne parafii rzymskokatolickiej Potok Wielki"
- Region: lubelskie, janowski
- Archive code: 0851d
- Lists all available units (jednostki)

### 2. Unit Index (jednostka)
**URL**: `https://skanoteka.genealodzy.pl/id5362-sy3500`
- Shows thumbnails/links for all images in the unit
- Example unit 3500: U-1750-1777 (175 files)
- Links to individual image viewers

### 3. Image Viewer
**URL**: `https://skanoteka.genealodzy.pl/index.php?op=pg&id=5362&sy=3500&kt=1&plik=000.jpg`
- Full viewer page with canvas-based image display
- Navigation buttons for next/previous

## Available Units in Collection id5362

| # | Unit | Description | Files |
|---|------|-------------|-------|
| 1 | 3500 | U-1750-1777 | 175 |
| 2 | 3505 | U-1777-1793 | - |
| 3 | 3510 | U-1777-1796 | - |
| 4 | 3515 | U-1797-1812 | - |
| 5 | 3520 | U-1813-1833 | - |
| 6 | 3525 | U-1826-1832 | - |
| 7 | 3530 | U-1833-1850 | - |
| 8 | 3535 | U-1851-1864 | - |
| 9 | 3540 | U-1864-1873 | - |
| 10 | 3545 | U-1873-1881 | - |
| 11 | 3550 | U-1881-1886 | - |
| 12 | 3555 | U-1885-1891-Raptularz | - |
| 13 | 3560 | U-1886-1889 | - |
| 14 | 3565 | U-1889 | - |
| 15 | 4500 | M-1727-1750 | - |
| 16 | 4505 | M-1750-1797 | - |
| 17 | 4510 | M-1797-1815 | - |
| 18 | 4515 | M-1812-1829 | - |

## Image Viewer Technical Details

### Image Loading Mechanism
```javascript
imageObj.src = 'https://metbox3.genealodzy.pl/metryka_get.php?dir=wxskBtJ7iGP0vTNJAIwwlT79eKnDi8Ts80G3Igs1KvUxtAApODZxypCZfL_45vAu-bMhsMgQ3jPc_0QfvEIf1A,,&znak=QetVSxxqFsEFAs_WV9Y71A,,&plik=000.jpg'.replace(/&amp;/g, '&');
```

- Images are served from **metbox3.genealodzy.pl** 
- Uses encrypted/encoded parameters (`dir`, `znak`)
- Actual filename is in the `plik` parameter

### Navigation Mechanism
```javascript
var imageLink = 'index.php?op=pg&amp;id=5362&amp;se=&amp;sy=3500&amp;kt=1&amp;plik=';

function nextImage() {
    window.location = (imageLink + '000a.jpg' + '&zoom=' + Scale + tagging).replace(/&amp;/g, '&');
}

function prevImage() {
    window.location = (imageLink + 'zzz.jpg' + '&zoom=' + Scale + tagging).replace(/&amp;/g, '&');
}
```

**Key Navigation Details:**
- **Next image**: Uses special filename `'000a.jpg'` appended to imageLink
- **Previous image**: Uses special filename `'zzz.jpg'`
- The server interprets these special filenames to navigate
- Current filename is `000.jpg`, but server tracks position
- Zoom level is preserved via `&zoom=` parameter

### Navigation Button
```html
<div class="button" onclick="nextImage()">Następne zdjęcie</div>
<div class="button" onclick="prevImage()">Poprzednie zdjęcie</div>
```

## Differences from Old Site (metryki.genealodzy.pl)

| Aspect | Old Site | New Site (skanoteka) |
|--------|----------|---------------------|
| **Domain** | metryki.genealodzy.pl | skanoteka.genealodzy.pl |
| **Image Server** | Same domain | metbox3.genealodzy.pl |
| **URL Parameters** | Direct file reference | Encrypted dir/znak params |
| **Navigation** | Similar button structure | Special filenames (000a.jpg/zzz.jpg) |
| **Structure** | ? | 3-level hierarchy |

## Issues with Current Scraper

### 1. **Wrong Start URL**
- Current: Points to collection index (`id5362`)
- Should be: Direct link to first image viewer
- Example: `https://skanoteka.genealodzy.pl/index.php?op=pg&id=5362&sy=3500&kt=1&plik=000.jpg`

### 2. **Navigation Method Compatibility**
- The `nextImage()` function uses `window.location` assignment, not href navigation
- Clicking the button should still work with Selenium
- XPath selector looks for "Następne" which matches "Następne zdjęcie" ✓

### 3. **Image URL Pattern**
- Old scraper looks for: `imageObj\.src\s*=\s*['\"]([^'\"]+)['\"]`
- New site uses: Same pattern ✓
- But URL points to metbox3.genealodzy.pl with encrypted parameters

## Recommendations

### Option 1: Single Unit Scraper
Update START_URL to point to first image in a specific unit:
```python
START_URL = "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5362&sy=3500&kt=1&plik=000.jpg"
```

### Option 2: Multi-Unit Scraper
1. Start at collection index
2. Extract all unit links
3. For each unit, get first image link
4. Scrape all images in unit
5. Move to next unit

### Option 3: Parameterized Scraper
Allow user to specify:
- Collection ID (5362)
- Unit number (3500)
- Start file (000.jpg)

## Testing Recommendations

1. **Test URL**: `https://skanoteka.genealodzy.pl/index.php?op=pg&id=5362&sy=3500&kt=1&plik=000.jpg`
2. **Verify navigation button clicking works** with current XPath
3. **Verify image URL extraction** from new metbox3 URLs
4. **Test loop detection** (unit 3500 has 175 images)
5. **Check if navigation wraps** or shows different "end" state

## Next Steps

1. Update START_URL to point to first image viewer (not collection index)
2. Test navigation mechanism compatibility
3. Verify image download from metbox3.genealodzy.pl
4. Consider adding unit switching logic if multi-unit scraping is desired
