import os
import time
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
COLLECTION_URL = "https://skanoteka.genealodzy.pl/id5362"
BASE_URL = "https://skanoteka.genealodzy.pl"
DOWNLOAD_FOLDER = "/app/watched-images"
MAX_IMAGES_PER_UNIT = 999  # Maximum images to download per unit

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

options = webdriver.ChromeOptions()
# options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

driver = webdriver.Chrome(options=options)

# --- GLOBAL TRACKING ---
total_images_downloaded = 0
units_processed = 0

def extract_units_from_collection(url):
    """Extract all unit links from the collection index page."""
    print(f"\n=== EXTRACTING UNITS FROM COLLECTION ===")
    print(f"Collection URL: {url}")
    
    driver.get(url)
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
    
    driver.get(unit_url)
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
    
    driver.get(start_url)
    
    for i in range(MAX_IMAGES_PER_UNIT):
        print(f"\n--- Processing image {i+1} in unit {unit_info['number']} ---")
        
        # Wait for page to load
        time.sleep(4)
        
        current_page_url = driver.current_url
        print(f"Current page URL: {current_page_url}")
        
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
