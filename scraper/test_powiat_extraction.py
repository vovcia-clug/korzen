import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# Configuration
POWIAT_URL = "https://metryki.genealodzy.pl/pow-24"
METRYKI_BASE_URL = "https://metryki.genealodzy.pl"

print("=== INITIALIZING CHROME DRIVER ===")

options = webdriver.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-setuid-sandbox')
options.add_argument('--remote-debugging-port=9222')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
options.add_argument('--disable-gpu')
options.add_argument('--window-size=1920,1080')
options.add_argument('--start-maximized')
options.binary_location = '/snap/chromium/current/usr/lib/chromium-browser/chrome'

try:
    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    driver = webdriver.Chrome(service=service, options=options)
    print("✓ Chrome driver initialized successfully")
except Exception as e:
    print(f"⚠️  webdriver-manager failed: {e}")
    driver = webdriver.Chrome(options=options)
    print("✓ Chrome driver initialized with system driver")

try:
    print(f"\n=== TESTING POWIAT NAME EXTRACTION ===")
    print(f"URL: {POWIAT_URL}")
    
    driver.get(POWIAT_URL)
    time.sleep(3)
    
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Extract powiat identifier from URL (e.g., pow-24)
    powiat_name = "unknown"
    url_match = re.search(r'(pow-\d+)', POWIAT_URL)
    if url_match:
        powiat_name = url_match.group(1)
        print(f"✓ Extracted powiat identifier from URL: '{powiat_name}'")
    else:
        print(f"⚠️  Could not extract powiat identifier from URL: {POWIAT_URL}")
    
    print(f"\n=== FINAL RESULT ===")
    print(f"Powiat name: {powiat_name}")
    
    # Now test collection extraction
    print(f"\n=== TESTING COLLECTION EXTRACTION ===")
    collection_links = soup.find_all('a', href=re.compile(r'^id\d+$'))
    print(f"Found {len(collection_links)} collection links")
    
    for i, link in enumerate(collection_links[:5], 1):
        href = link.get('href')
        collection_id_match = re.search(r'^id(\d+)$', href)
        if collection_id_match:
            collection_id = collection_id_match.group(1)
            collection_url = METRYKI_BASE_URL + '/' + href
            collection_name = link.text.strip()
            print(f"  {i}. Collection {collection_id}: {collection_name} -> {collection_url}")

finally:
    print("\n=== CLOSING BROWSER ===")
    driver.quit()
    print("Done!")
