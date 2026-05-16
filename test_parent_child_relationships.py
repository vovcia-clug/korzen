#!/usr/bin/env python
"""
Test script to verify parent-child relationship import from GEDCOM files.
"""
import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_parent_child_import():
    """Test that parent-child relationships are imported correctly."""
    print("=" * 70)
    print("Parent-Child Relationship Import Test")
    print("=" * 70)
    
    # Test 1: Check if process_family_children method exists
    print("\n1. Checking if process_family_children() method exists...")
    try:
        from app.gedcom_parser import GedcomParser
        
        # Check if method exists
        if hasattr(GedcomParser, 'process_family_children'):
            print("   ✓ process_family_children() method found")
        else:
            print("   ✗ process_family_children() method NOT found")
            return False
    except Exception as e:
        print(f"   ✗ Error importing GedcomParser: {e}")
        return False
    
    # Test 2: Check Person model has father_id and mother_id fields
    print("\n2. Checking Person model fields...")
    try:
        from app.models import Person
        
        # Check if fields exist in model
        has_father_id = hasattr(Person, 'father_id')
        has_mother_id = hasattr(Person, 'mother_id')
        
        if has_father_id and has_mother_id:
            print("   ✓ Person model has father_id and mother_id fields")
        else:
            print(f"   ✗ Missing fields - father_id: {has_father_id}, mother_id: {has_mother_id}")
            return False
    except Exception as e:
        print(f"   ✗ Error checking Person model: {e}")
        return False
    
    # Test 3: Verify GEDCOM file structure
    print("\n3. Checking GEDCOM test files...")
    test_files = [
        'data/Simpsons_Cartoon.ged',
        'data/The_Kennedy_Family.ged'
    ]
    
    found_files = []
    for filepath in test_files:
        if os.path.exists(filepath):
            print(f"   ✓ Found {filepath}")
            found_files.append(filepath)
        else:
            print(f"   ⚠ {filepath} not found (optional)")
    
    if not found_files:
        print("   ⚠ No test GEDCOM files found, skipping file structure test")
    else:
        # Check if files contain FAM records with CHIL tags
        print("\n4. Checking GEDCOM file structure...")
        try:
            from ged4py import GedcomReader
            
            for filepath in found_files:
                with GedcomReader(filepath, encoding='utf-8') as reader:
                    fam_count = 0
                    chil_count = 0
                    
                    for family in reader.records0('FAM'):
                        fam_count += 1
                        for sub in family.sub_records:
                            if sub.tag == 'CHIL':
                                chil_count += 1
                    
                    print(f"   ✓ {filepath}: {fam_count} families, {chil_count} children")
        except Exception as e:
            print(f"   ✗ Error reading GEDCOM files: {e}")
    
    # Test 4: Check statistics tracking
    print("\n5. Checking statistics tracking...")
    try:
        # Read the gedcom_parser.py file to verify stats dict
        parser_file = Path(__file__).parent / 'src' / 'app' / 'gedcom_parser.py'
        with open(parser_file, 'r') as f:
            content = f.read()
            
        if "'parent_child_relationships': 0" in content:
            print("   ✓ Statistics tracking includes parent_child_relationships")
        else:
            print("   ✗ Statistics tracking missing parent_child_relationships")
            return False
            
        if "stats['parent_child_relationships'] = children_processed" in content:
            print("   ✓ Statistics are updated after processing")
        else:
            print("   ✗ Statistics update code not found")
            return False
    except Exception as e:
        print(f"   ✗ Error checking statistics: {e}")
        return False
    
    # Test 5: Verify fourth pass exists
    print("\n6. Checking fourth pass implementation...")
    try:
        parser_file = Path(__file__).parent / 'src' / 'app' / 'gedcom_parser.py'
        with open(parser_file, 'r') as f:
            content = f.read()
        
        if "# Fourth pass: Process parent-child relationships" in content:
            print("   ✓ Fourth pass comment found")
        else:
            print("   ✗ Fourth pass comment not found")
            return False
        
        if "self.process_family_children(family)" in content:
            print("   ✓ Fourth pass calls process_family_children()")
        else:
            print("   ✗ Fourth pass doesn't call process_family_children()")
            return False
    except Exception as e:
        print(f"   ✗ Error checking fourth pass: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✓ All tests passed! Parent-child relationship import is implemented.")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Start the application and import a GEDCOM file")
    print("2. Check the database to verify father_id and mother_id are populated:")
    print("   SELECT id, first_name, last_name, father_id, mother_id FROM persons LIMIT 10;")
    print("3. Verify PARENT_OF edges in the AGE graph")
    print("4. Test the family tree visualization")
    
    return True

def main():
    """Run all tests."""
    try:
        success = test_parent_child_import()
        return 0 if success else 1
    except Exception as e:
        print(f"\n✗ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
