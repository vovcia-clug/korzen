#!/usr/bin/env python
"""
Test script for GEDCOM parser functionality.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ged4py import GedcomReader

def test_gedcom_reading():
    """Test basic GEDCOM file reading."""
    print("Testing GEDCOM file reading...")
    
    test_files = ['test_sample.ged', 'Habsburg.ged']
    
    for filename in test_files:
        if not os.path.exists(filename):
            print(f"  ⚠ Skipping {filename} (not found)")
            continue
            
        try:
            with GedcomReader(filename, encoding='utf-8') as reader:
                # Count records
                indi_count = sum(1 for _ in reader.records0('INDI'))
                
            with GedcomReader(filename, encoding='utf-8') as reader:
                fam_count = sum(1 for _ in reader.records0('FAM'))
                
            print(f"  ✓ {filename}: {indi_count} individuals, {fam_count} families")
            
            # Show sample individual
            with GedcomReader(filename, encoding='utf-8') as reader:
                for individual in reader.records0('INDI'):
                    name = individual.name[0].value if individual.name else "Unknown"
                    sex = individual.sex.value if individual.sex else "Unknown"
                    print(f"    Sample person: {name} ({sex})")
                    break
                    
        except Exception as e:
            print(f"  ✗ Error reading {filename}: {e}")
            return False
    
    return True

def test_parser_imports():
    """Test that parser module can be imported."""
    print("\nTesting parser imports...")
    
    try:
        from app.gedcom_parser import GedcomParser
        print("  ✓ GedcomParser imported successfully")
        return True
    except Exception as e:
        print(f"  ✗ Failed to import GedcomParser: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("GEDCOM Parser Test Suite")
    print("=" * 60)
    
    tests = [
        test_gedcom_reading,
        test_parser_imports,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    return 0 if all(results) else 1

if __name__ == '__main__':
    sys.exit(main())
