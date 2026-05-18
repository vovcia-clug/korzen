#!/usr/bin/env python3
"""
Standalone test script for Skanoteka metadata extraction functionality.
This script contains a copy of the extraction function to avoid import issues.
"""

import json
import re
import requests
from bs4 import BeautifulSoup


def extract_metadata_from_url(url):
    """
    Extract metadata from a Skanoteka page URL.
    
    Args:
        url (str): The Skanoteka page URL to extract metadata from
        
    Returns:
        dict: Metadata in JSON format with keys: place, unit, years, page
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


def main():
    """Run the metadata extraction test."""
    
    test_url = "https://skanoteka.genealodzy.pl/index.php?op=pg&id=5545&se=&sy=4500&kt=1&plik=301.jpg&x=0&y=0&zoom=1.0"
    
    print("="*80)
    print("TESTING METADATA EXTRACTION")
    print("="*80)
    print(f"\nTest URL: {test_url}\n")
    
    # Extract metadata
    metadata = extract_metadata_from_url(test_url)
    
    # Display results
    print("\n" + "="*80)
    print("EXTRACTED METADATA (JSON FORMAT):")
    print("="*80)
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    
    # Validate results
    print("\n" + "="*80)
    print("VALIDATION:")
    print("="*80)
    
    expected_fields = ['place', 'unit', 'years', 'page']
    all_present = all(field in metadata for field in expected_fields)
    
    if all_present:
        print("✓ All expected fields present")
    else:
        print("✗ Missing fields")
        missing = [f for f in expected_fields if f not in metadata]
        print(f"  Missing: {missing}")
    
    # Check if any values were extracted
    has_values = all(metadata.get(field) is not None for field in expected_fields)
    
    if has_values:
        print("✓ All fields have values")
    else:
        print("⚠️  Some fields are missing values")
        for field in expected_fields:
            if metadata.get(field) is None:
                print(f"  - {field}: None")
    
    # Check for errors
    if 'error' in metadata:
        print(f"⚠️  Error occurred: {metadata['error']}")
        return False
    else:
        print("✓ No errors")
    
    # Detailed field check
    print("\n" + "="*80)
    print("FIELD DETAILS:")
    print("="*80)
    
    for field in expected_fields:
        value = metadata.get(field)
        status = "✓" if value else "✗"
        print(f"{status} {field}: {value}")
    
    print("\n" + "="*80)
    print("TEST PASSED" if has_values and not metadata.get('error') else "TEST FAILED")
    print("="*80)
    
    return has_values and not metadata.get('error')


if __name__ == "__main__":
    import sys
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
