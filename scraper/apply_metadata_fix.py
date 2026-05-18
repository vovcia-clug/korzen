#!/usr/bin/env python3
"""
Script to apply the metadata saving fix to scraper.py
"""

import re

print("="*80)
print("APPLYING METADATA SAVING FIX")
print("="*80)

# Read the original file
with open('scraper.py', 'r') as f:
    content = f.read()

original_content = content

# Fix #1: Add metadata extraction after getting current_page_url
# Find the location after "print(f"Current page URL: {current_page_url}")"
pattern1 = r'(current_page_url = driver\.current_url\s+print\(f"Current page URL: \{current_page_url\}"\)\s+)(# Extract image URL from JavaScript)'

replacement1 = r'\1# Extract metadata from current page\n        metadata = extract_metadata_from_driver(driver)\n        print(f"Extracted metadata: Place={metadata.get(\'place\')}, Unit={metadata.get(\'unit\')}, Page={metadata.get(\'page\')}")\n        \n        \2'

content = re.sub(pattern1, replacement1, content)

if content != original_content:
    print("✓ Fix #1 applied: Added metadata extraction in scraping loop")
else:
    print("⚠️  Fix #1 not applied - pattern not found or already applied")

# Fix #2: Add metadata saving before downloading image
# Find the location after "filepath = os.path.join(unit_folder, filename)"
pattern2 = r'(filepath = os\.path\.join\(unit_folder, filename\)\s+)(# Download image)'

replacement2 = r'''\1# Save metadata to JSON file
            metadata_filepath = os.path.splitext(filepath)[0] + '_metadata.json'
            try:
                with open(metadata_filepath, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                print(f"✓ Saved metadata: {metadata_filepath}")
            except Exception as e:
                print(f"⚠️  Error saving metadata: {e}")
            
            \2'''

original_before_fix2 = content
content = re.sub(pattern2, replacement2, content)

if content != original_before_fix2:
    print("✓ Fix #2 applied: Added metadata saving to JSON files")
else:
    print("⚠️  Fix #2 not applied - pattern not found or already applied")

# Write the modified content back
if content != original_content:
    with open('scraper.py', 'w') as f:
        f.write(content)
    print("\n" + "="*80)
    print("✓ SUCCESS: scraper.py has been updated with metadata saving functionality")
    print("="*80)
    print("\nChanges made:")
    print("1. Added metadata extraction in the scraping loop (after line ~380)")
    print("2. Added metadata saving to JSON files (after line ~419)")
    print("\nMetadata will now be saved as: <image_name>_metadata.json")
else:
    print("\n" + "="*80)
    print("⚠️  NO CHANGES MADE: Fixes may already be applied or patterns not found")
    print("="*80)
