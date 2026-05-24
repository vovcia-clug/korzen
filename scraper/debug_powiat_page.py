import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# Configuration
POWIAT_URL = "https://metryki.genealodzy.pl/pow-24"

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
    print(f"\n=== NAVIGATING TO POWIAT PAGE ===")
    print(f"URL: {POWIAT_URL}")
    
    driver.get(POWIAT_URL)
    print(f"Current URL: {driver.current_url}")
    print(f"Page title: {driver.title}")
    
    time.sleep(3)
    
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Save full HTML for inspection
    with open('powiat_page_debug.html', 'w', encoding='utf-8') as f:
        f.write(soup.prettify())
    print("\n✓ Saved full HTML to: powiat_page_debug.html")
    
    # Analyze all links on the page
    print("\n=== ANALYZING ALL LINKS ON PAGE ===")
    all_links = soup.find_all('a', href=True)
    print(f"Total links found: {len(all_links)}")
    
    # Group links by pattern
    link_patterns = {}
    for link in all_links:
        href = link.get('href', '')
        text = link.text.strip()
        
        # Categorize by pattern
        if '/id' in href:
            pattern = 'Contains /id'
        elif 'pow-' in href:
            pattern = 'Contains pow-'
        elif href.startswith('http'):
            pattern = 'External link'
        elif href.startswith('/'):
            pattern = 'Absolute path'
        else:
            pattern = 'Relative path'
        
        if pattern not in link_patterns:
            link_patterns[pattern] = []
        
        link_patterns[pattern].append({
            'href': href,
            'text': text[:50] if text else '(no text)'
        })
    
    # Print summary
    print("\n=== LINK PATTERNS SUMMARY ===")
    for pattern, links in link_patterns.items():
        print(f"\n{pattern}: {len(links)} links")
        for i, link in enumerate(links[:5], 1):  # Show first 5 of each type
            print(f"  {i}. href='{link['href'][:80]}' text='{link['text']}'")
        if len(links) > 5:
            print(f"  ... and {len(links) - 5} more")
    
    # Look specifically for collection-like links
    print("\n=== SEARCHING FOR COLLECTION LINKS ===")
    
    # Pattern 1: /id followed by numbers
    pattern1 = soup.find_all('a', href=re.compile(r'/id\d+'))
    print(f"\nPattern '/id\\d+': {len(pattern1)} matches")
    for i, link in enumerate(pattern1[:10], 1):
        print(f"  {i}. {link.get('href')} - {link.text.strip()[:50]}")
    
    # Pattern 2: id= parameter
    pattern2 = soup.find_all('a', href=re.compile(r'id=\d+'))
    print(f"\nPattern 'id=\\d+': {len(pattern2)} matches")
    for i, link in enumerate(pattern2[:10], 1):
        print(f"  {i}. {link.get('href')} - {link.text.strip()[:50]}")
    
    # Pattern 3: Look for table rows with collection data
    print("\n=== SEARCHING FOR TABLES ===")
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables")
    
    for idx, table in enumerate(tables, 1):
        rows = table.find_all('tr')
        print(f"\nTable {idx}: {len(rows)} rows")
        if rows:
            # Show first few rows
            for i, row in enumerate(rows[:3], 1):
                cells = row.find_all(['td', 'th'])
                cell_texts = [cell.text.strip()[:30] for cell in cells]
                print(f"  Row {i}: {' | '.join(cell_texts)}")
            if len(rows) > 3:
                print(f"  ... and {len(rows) - 3} more rows")

finally:
    print("\n=== CLOSING BROWSER ===")
    driver.quit()
    print("Done!")
