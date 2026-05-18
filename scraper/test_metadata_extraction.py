#!/usr/bin/env python3
"""
Test script for Skanoteka metadata extraction functionality.
Tests the extract_metadata_from_url function with a sample URL.
"""

import json
import sys
import os

# Add scraper directory to path
sys.path.insert(0, os.path.dirname(__file__))

from scraper import extract_metadata_from_url

def test_metadata_extraction():
    """Test metadata extraction with the provided URL."""
    
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
    has_values = any(metadata.get(field) is not None for field in expected_fields)
    
    if has_values:
        print("✓ At least one field has a value")
    else:
        print("✗ No values extracted")
    
    # Check for errors
    if 'error' in metadata:
        print(f"⚠️  Error occurred: {metadata['error']}")
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
    
    return metadata

if __name__ == "__main__":
    try:
        metadata = test_metadata_extraction()
        
        # Exit with appropriate code
        if metadata and not metadata.get('error'):
            print("\n" + "="*80)
            print("TEST PASSED")
            print("="*80)
            sys.exit(0)
        else:
            print("\n" + "="*80)
            print("TEST FAILED")
            print("="*80)
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
