#!/usr/bin/env python3
"""
Diagnostic script to identify why metadata is not being saved with files.

This script analyzes the scraper.py code to identify the root cause.
"""

import re

print("="*80)
print("METADATA SAVING ISSUE DIAGNOSIS")
print("="*80)

# Read the scraper.py file
with open('scraper.py', 'r') as f:
    content = f.read()

print("\n1. CHECKING IF METADATA EXTRACTION FUNCTIONS EXIST...")
print("-" * 80)

# Check if metadata extraction functions are defined
if 'def extract_metadata_from_url' in content:
    print("✓ extract_metadata_from_url() function is DEFINED")
else:
    print("✗ extract_metadata_from_url() function is NOT DEFINED")

if 'def extract_metadata_from_driver' in content:
    print("✓ extract_metadata_from_driver() function is DEFINED")
else:
    print("✗ extract_metadata_from_driver() function is NOT DEFINED")

print("\n2. CHECKING IF METADATA EXTRACTION IS CALLED IN SCRAPING LOOP...")
print("-" * 80)

# Find the scrape_unit_images function
scrape_func_match = re.search(r'def scrape_unit_images\(.*?\):(.*?)(?=\ndef |\Z)', content, re.DOTALL)

if scrape_func_match:
    scrape_func_body = scrape_func_match.group(1)
    
    # Check if metadata extraction is called
    if 'extract_metadata_from_driver' in scrape_func_body:
        print("✓ extract_metadata_from_driver() IS CALLED in scrape_unit_images()")
    else:
        print("✗ extract_metadata_from_driver() IS NOT CALLED in scrape_unit_images()")
        print("   → ROOT CAUSE #1: Metadata extraction function exists but is never invoked!")
    
    if 'extract_metadata_from_url' in scrape_func_body:
        print("✓ extract_metadata_from_url() IS CALLED in scrape_unit_images()")
    else:
        print("✗ extract_metadata_from_url() IS NOT CALLED in scrape_unit_images()")

print("\n3. CHECKING IF METADATA IS SAVED TO FILES...")
print("-" * 80)

# Check if there's code to save metadata to JSON files
if scrape_func_match:
    scrape_func_body = scrape_func_match.group(1)
    
    # Look for JSON file writing
    if re.search(r'json\.dump.*metadata', scrape_func_body):
        print("✓ Code EXISTS to save metadata to JSON files")
    else:
        print("✗ Code DOES NOT EXIST to save metadata to JSON files")
        print("   → ROOT CAUSE #2: No code to write metadata to disk!")
    
    # Look for metadata file path creation
    if '_metadata.json' in scrape_func_body:
        print("✓ Metadata file path is created")
    else:
        print("✗ Metadata file path is NOT created")

print("\n4. SUMMARY OF FINDINGS")
print("="*80)

issues_found = []

# Issue 1: Metadata extraction not called
if scrape_func_match and 'extract_metadata_from_driver' not in scrape_func_match.group(1):
    issues_found.append({
        'issue': 'Metadata extraction function is never called',
        'location': 'scrape_unit_images() function',
        'impact': 'Metadata is never extracted from pages',
        'fix': 'Add call to extract_metadata_from_driver(driver) in the scraping loop'
    })

# Issue 2: No code to save metadata
if scrape_func_match and not re.search(r'json\.dump.*metadata', scrape_func_match.group(1)):
    issues_found.append({
        'issue': 'No code to save metadata to files',
        'location': 'scrape_unit_images() function, after image download',
        'impact': 'Even if metadata were extracted, it would not be saved',
        'fix': 'Add code to write metadata to JSON files alongside images'
    })

if issues_found:
    print(f"\n🔴 FOUND {len(issues_found)} CRITICAL ISSUE(S):\n")
    for i, issue in enumerate(issues_found, 1):
        print(f"Issue #{i}: {issue['issue']}")
        print(f"  Location: {issue['location']}")
        print(f"  Impact: {issue['impact']}")
        print(f"  Fix: {issue['fix']}")
        print()
else:
    print("\n✓ No issues found - metadata should be saving correctly")

print("\n5. RECOMMENDED SOLUTION")
print("="*80)
print("""
To fix the metadata saving issue, two changes are needed:

1. EXTRACT METADATA: Add metadata extraction in the scraping loop
   Location: After line ~380 (after getting current_page_url)
   Code to add:
   ```python
   metadata = extract_metadata_from_driver(driver)
   ```

2. SAVE METADATA: Add code to save metadata to JSON files
   Location: After line ~419 (after setting filepath, before downloading image)
   Code to add:
   ```python
   # Save metadata to JSON file
   metadata_filepath = os.path.splitext(filepath)[0] + '_metadata.json'
   with open(metadata_filepath, 'w', encoding='utf-8') as f:
       json.dump(metadata, f, indent=2, ensure_ascii=False)
   print(f"✓ Saved metadata: {metadata_filepath}")
   ```

This will create a JSON file for each image with the same base name.
Example: scan_001.jpg → scan_001_metadata.json
""")

print("\n" + "="*80)
print("DIAGNOSIS COMPLETE")
print("="*80)
