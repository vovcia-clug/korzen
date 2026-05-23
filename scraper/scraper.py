import os
import time
import re
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# --- CONFIGURATION ---
COLLECTION_URL = "https://metryki.genealodzy.pl/id1784"
BASE_URL = "https://skanoteka.genealodzy.pl"
DOWNLOAD_FOLDER = "/app/watched-images"
MAX_IMAGES_PER_UNIT = 1000  # Maximum images to download per unit

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

print("\n=== INITIALIZING CHROME DRIVER ===")

options = webdriver.ChromeOptions()
# options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# Critical fix for snap-installed Chromium
options.add_argument('--disable-setuid-sandbox')
options.add_argument('--remote-debugging-port=9222')

# Anti-detection options
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

# User agent
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# Additional stability options
options.add_argument('--disable-gpu')
options.add_argument('--window-size=1920,1080')
options.add_argument('--start-maximized')

# Set binary location for snap-installed Chromium
options.binary_location = '/snap/chromium/current/usr/lib/chromium-browser/chrome'

print(f"Chrome options configured:")
print(f"  - no-sandbox: enabled")
print(f"  - disable-dev-shm-usage: enabled")
print(f"  - disable-blink-features=AutomationControlled: enabled")
print(f"  - User-Agent: Mozilla/5.0...")

# Use webdriver-manager to automatically download and manage ChromeDriver
print("Installing/updating ChromeDriver to match Chromium version...")
try:
    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    driver = webdriver.Chrome(service=service, options=options)
    print(f"✓ Chrome driver initialized successfully with webdriver-manager")
except Exception as e:
    print(f"⚠️  webdriver-manager failed: {e}")
    print("Falling back to system ChromeDriver...")
    driver = webdriver.Chrome(options=options)
    print(f"✓ Chrome driver initialized with system driver")

# Remove webdriver property to avoid detection
try:
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    print(f"✓ Anti-detection measures applied")
except Exception as e:
    print(f"⚠️  Could not apply some anti-detection measures: {e}")

# --- GLOBAL TRACKING ---
total_images_downloaded = 0
units_processed = 0

def extract_metadata_from_url(url):
    """
    Extract metadata from a Skanoteka page URL.
    
    Args:
        url (str): The Skanoteka page URL to extract metadata from
        
    Returns:
        dict: Metadata in JSON format with keys: place, unit, years, page
        
    Example:
        >>> metadata = extract_metadata_from_url("https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg")
        >>> print(metadata)
        {'place': 'Bolechów', 'unit': '4500 M-1874-1937-Bolechów', 'years': '1874-1937', 'page': '301.jpg (301 z 303)'}
    """
    print(f"\n=== EXTRACTING METADATA FROM URL ===")
    print(f"URL: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the sidebar div containing metadata
        sidebar = soup.find('div', class_='sidebar')
        
        if not sidebar:
            print("⚠️  Warning: Could not find sidebar div")
            return {
                "place": None,
                "unit": None,
                "years": None,
                "page": None,
                "error": "Sidebar not found"
            }
        
        # Extract text content from sidebar
        sidebar_text = sidebar.get_text()
        
        # Extract metadata using regex patterns
        metadata = {}
        
        # Extract Miejscowość (place)
        place_match = re.search(r'Miejscowość:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['place'] = place_match.group(1).strip() if place_match else None
        
        # Extract Jednostka (unit)
        unit_match = re.search(r'Jednostka:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['unit'] = unit_match.group(1).strip() if unit_match else None
        
        # Extract Lata (years)
        years_match = re.search(r'Lata:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['years'] = years_match.group(1).strip() if years_match else None
        
        # Extract Plik (page/file)
        file_match = re.search(r'Plik:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['page'] = file_match.group(1).strip() if file_match else None
        
        print(f"✓ Metadata extracted successfully:")
        print(f"  - Place: {metadata['place']}")
        print(f"  - Unit: {metadata['unit']}")
        print(f"  - Years: {metadata['years']}")
        print(f"  - Page: {metadata['page']}")
        
        return metadata
        
    except requests.RequestException as e:
        print(f"✗ Error fetching URL: {e}")
        return {
            "place": None,
            "unit": None,
            "years": None,
            "page": None,
            "error": str(e)
        }
    except Exception as e:
        print(f"✗ Error extracting metadata: {e}")
        return {
            "place": None,
            "unit": None,
            "years": None,
            "page": None,
            "error": str(e)
        }

def extract_metadata_from_driver(driver):
    """
    Extract metadata from the current page loaded in Selenium driver.
    This is useful when already navigating pages with Selenium.
    
    Args:
        driver: Selenium WebDriver instance with page already loaded
        
    Returns:
        dict: Metadata in JSON format with keys: place, unit, years, page
    """
    try:
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find the sidebar div containing metadata
        sidebar = soup.find('div', class_='sidebar')
        
        if not sidebar:
            return {
                "place": None,
                "unit": None,
                "years": None,
                "page": None,
                "error": "Sidebar not found"
            }
        
        # Extract text content from sidebar
        sidebar_text = sidebar.get_text()
        
        # Extract metadata using regex patterns
        metadata = {}
        
        place_match = re.search(r'Miejscowość:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['place'] = place_match.group(1).strip() if place_match else None
        
        unit_match = re.search(r'Jednostka:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['unit'] = unit_match.group(1).strip() if unit_match else None
        
        years_match = re.search(r'Lata:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['years'] = years_match.group(1).strip() if years_match else None
        
        file_match = re.search(r'Plik:\s*\n\s*([^\n]+)', sidebar_text)
        metadata['page'] = file_match.group(1).strip() if file_match else None
        
        return metadata
        
    except Exception as e:
        return {
            "place": None,
            "unit": None,
            "years": None,
            "page": None,
            "error": str(e)
        }

def extract_units_from_collection(url):
    """Extract all unit links from the collection index page."""
    print(f"\n=== EXTRACTING UNITS FROM COLLECTION ===")
    print(f"Collection URL: {url}")
    
    print(f"DEBUG: Navigating to URL: {url}")
    driver.get(url)
    print(f"DEBUG: Current URL after navigation: {driver.current_url}")
    print(f"DEBUG: Page title: {driver.title}")
    print(f"DEBUG: Page source length: {len(driver.page_source)} characters")
    
    if driver.current_url == "data:,":
        print("✗ ERROR: Browser navigated to 'data:,' - URL navigation failed!")
        print("This usually indicates:")
        print("  1. Network connectivity issues")
        print("  2. Website blocking automated requests")
        print("  3. Invalid URL or DNS resolution failure")
        print("  4. Chrome driver configuration issues")
        return []
    
    time.sleep(3)
    
    units = []
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Find all links matching pattern: id5362-sy3500, id5362-sy3505, etc.
    unit_links = soup.find_all('a', href=re.compile(r'id\d+-sy\d+'))
    
    for link in unit_links:
        href = link.get('href')
        if not href:
            continue
        
        unit_url = str(href)
        if not unit_url.startswith('http'):
            unit_url = BASE_URL + '/' + unit_url.lstrip('/')
        
        # Extract unit description from the row
        row = link.find_parent('tr')
        unit_number = link.text.strip()
        description = "Unknown"
        file_count = "Unknown"
        
        if row:
            cells = row.find_all('td')
            if len(cells) >= 3:
                description = cells[2].text.strip()
            if len(cells) >= 5:
                file_count = cells[4].text.strip()
        
        units.append({
            'url': unit_url,
            'number': unit_number,
            'description': description,
            'file_count': file_count
        })
    
    print(f"Found {len(units)} units in collection")
    for i, unit in enumerate(units, 1):
        print(f"  {i}. Unit {unit['number']}: {unit['description']} ({unit['file_count']} files)")
    
    return units

def get_first_image_url_from_unit(unit_url):
    """Extract the first image viewer URL from a unit index page."""
    print(f"\n  → Getting first image from unit: {unit_url}")
    
    print(f"  DEBUG: Navigating to unit URL: {unit_url}")
    driver.get(unit_url)
    print(f"  DEBUG: Current URL after navigation: {driver.current_url}")
    print(f"  DEBUG: Page title: {driver.title}")
    
    if driver.current_url == "data:,":
        print("  ✗ ERROR: Browser navigated to 'data:,' - URL navigation failed!")
        return None
    
    time.sleep(3)
    
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Find first link with class="plik" and target="doc"
    first_image_link = soup.find('a', class_='plik', target='doc')
    
    if first_image_link:
        href = first_image_link.get('href')
        if not href:
            print(f"  ⚠️  Image link has no href attribute")
            return None
        
        href_str = str(href)
        if not href_str.startswith('http'):
            # Handle relative URLs
            if href_str.startswith('index.php'):
                image_url = BASE_URL + '/' + href_str
            else:
                image_url = BASE_URL + '/' + href_str.lstrip('/')
        else:
            image_url = href_str
        
        # Ensure zoom=1.0 parameter is present
        if 'zoom=' not in image_url:
            # Add zoom parameter
            separator = '&' if '?' in image_url else '?'
            image_url = f"{image_url}{separator}zoom=1.0"
        elif 'zoom=' in image_url:
            # Replace existing zoom parameter with zoom=1.0
            image_url = re.sub(r'zoom=[^&]*', 'zoom=1.0', image_url)
        
        print(f"  → First image URL: {image_url}")
        return image_url
    else:
        print(f"  ⚠️  No image links found in unit")
        return None

def scrape_unit_images(start_url, unit_info):
    """Scrape all images from a single unit."""
    global total_images_downloaded
    
    print(f"\n{'='*80}")
    print(f"SCRAPING UNIT: {unit_info['number']} - {unit_info['description']}")
    print(f"Expected files: {unit_info['file_count']}")
    print(f"{'='*80}")
    
    # Create subdirectory for this unit
    unit_folder = os.path.join(DOWNLOAD_FOLDER, f"unit_{unit_info['number']}")
    if not os.path.exists(unit_folder):
        os.makedirs(unit_folder)
    
    # Track visited URLs and filenames for this unit
    visited_image_urls = set()
    downloaded_filenames = set()
    unit_images_count = 0
    
    print(f"DEBUG: Navigating to start URL: {start_url}")
    driver.get(start_url)
    print(f"DEBUG: Current URL after navigation: {driver.current_url}")
    print(f"DEBUG: Page title: {driver.title}")
    
    if driver.current_url == "data:,":
        print("✗ ERROR: Browser navigated to 'data:,' - cannot scrape images!")
        return 0
    
    for i in range(MAX_IMAGES_PER_UNIT):
        print(f"\n--- Processing image {i+1} in unit {unit_info['number']} ---")
        
        # Wait for page to load
        time.sleep(4)
        
        current_page_url = driver.current_url
        print(f"Current page URL: {current_page_url}")
        
        # Extract metadata from current page
        metadata = extract_metadata_from_driver(driver)
        print(f"Extracted metadata: Place={metadata.get('place')}, Unit={metadata.get('unit')}, Page={metadata.get('page')}")
        
        # Extract image URL from JavaScript
        page_source = driver.page_source
        img_url = None
        
        img_url_match = re.search(r"imageObj\.src\s*=\s*['\"]([^'\"]+)['\"]", page_source)
        
        if img_url_match:
            img_url = img_url_match.group(1)
            img_url = img_url.replace('&amp;', '&')
            print(f"Found image URL: {img_url}")
        else:
            print("Could not find imageObj.src in page")
        
        if img_url:
            # Loop detection
            if img_url in visited_image_urls:
                print(f"⚠️  LOOP DETECTED: Image URL already seen")
                print(f"✓ Downloaded {unit_images_count} images from unit {unit_info['number']}")
                break
            
            visited_image_urls.add(img_url)
            
            # Derive filename from plik parameter in URL
            plik_match = re.search(r'plik=([^&]+)', current_page_url)
            if plik_match:
                filename = plik_match.group(1)
            else:
                # Fallback to sequential naming
                filename = f"scan_{i+1:03d}.jpg"
            
            # Check filename loop
            if filename in downloaded_filenames:
                print(f"⚠️  LOOP DETECTED: Filename already downloaded: {filename}")
                print(f"✓ Downloaded {unit_images_count} images from unit {unit_info['number']}")
                break
            
            downloaded_filenames.add(filename)
            filepath = os.path.join(unit_folder, filename)
            
            # Save metadata to JSON file
            metadata_filepath = os.path.splitext(filepath)[0] + '.json'
            try:
                with open(metadata_filepath, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                print(f"✓ Saved metadata: {metadata_filepath}")
            except Exception as e:
                print(f"⚠️  Error saving metadata: {e}")
            
            # Download image
            try:
                session = requests.Session()
                for cookie in driver.get_cookies():
                    session.cookies.set(cookie['name'], cookie['value'])
                
                headers = {'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                response = session.get(img_url, headers=headers)
                
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    print(f"✓ Saved: {filepath}")
                    unit_images_count += 1
                    total_images_downloaded += 1
                else:
                    print(f"✗ Failed download. Status code: {response.status_code}")
            except Exception as e:
                print(f"✗ Error saving file: {e}")
        else:
            print("Could not extract image URL")
        
        # Navigate to next image
        try:
            print("Attempting to click 'Next' button...")
            next_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='button' and contains(text(), 'Następne')]"))
            )
            
            driver.execute_script("arguments[0].click();", next_button)
            print("✓ Clicked 'Next' button")
            
        except Exception as e:
            print(f"Navigation failed: {type(e).__name__}")
            print("No 'Next' button found - reached end of unit")
            break
    
    print(f"\n{'='*80}")
    print(f"UNIT {unit_info['number']} COMPLETE: Downloaded {unit_images_count} images")
    print(f"{'='*80}")
    
    return unit_images_count

try:
    # Step 1: Extract all units from collection
    units = extract_units_from_collection(COLLECTION_URL)
    
    if not units:
        print("⚠️  No units found in collection!")
    else:
        # Step 2: Process each unit
        for i, unit in enumerate(units, 1):
            print(f"\n{'#'*80}")
            print(f"# PROCESSING UNIT {i}/{len(units)}")
            print(f"{'#'*80}")
            
            # Get first image URL for this unit
            first_image_url = get_first_image_url_from_unit(unit['url'])
            
            if first_image_url:
                # Scrape all images in this unit
                images_in_unit = scrape_unit_images(first_image_url, unit)
                units_processed += 1
            else:
                print(f"⚠️  Skipping unit {unit['number']} - no images found")
            
            print(f"\n--- Progress: {units_processed}/{len(units)} units, {total_images_downloaded} total images ---")

finally:
    print(f"\n{'='*80}")
    print("SCRAPING COMPLETE")
    print(f"{'='*80}")
    print(f"Units processed: {units_processed}")
    print(f"Total images downloaded: {total_images_downloaded}")
    print(f"Download folder: {DOWNLOAD_FOLDER}")
    print("\nClosing browser session.")
    driver.quit()
