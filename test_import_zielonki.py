#!/usr/bin/env python3
"""
Direct test of zielonki.ged import to capture the exact error.
"""
import sys
import os

# Add src to path
sys.path.insert(0, 'src')

# Mock Flask app minimum setup
os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/family_tree'
os.environ['SECRET_KEY'] = 'test-key'

try:
    print("Attempting to import ged4py and parse zielonki.ged...")
    print("="*70)
    
    from ged4py import GedcomReader
    
    filepath = 'data/zielonki.ged'
    
    # Try parsing with different encodings
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        print(f"\nTrying encoding: {encoding}")
        print("-"*70)
        try:
            with GedcomReader(filepath, encoding=encoding) as reader:
                count = 0
                for record in reader.records0('INDI'):
                    count += 1
                    if count <= 1:
                        print(f"  First record: {record.xref_id}")
                
                print(f"✓ Success! Parsed {count} individuals with {encoding}")
                break
                
        except Exception as e:
            print(f"✗ Error with {encoding}:")
            print(f"  Type: {type(e).__name__}")
            print(f"  Message: {str(e)}")
            
            # Get detailed traceback
            import traceback
            tb = traceback.format_exc()
            # Print last few lines of traceback
            tb_lines = tb.split('\n')
            for line in tb_lines[-10:]:
                if line.strip():
                    print(f"  {line}")
            print()

except ImportError as e:
    print(f"Cannot import ged4py: {e}")
    print("\nThis script requires running in an environment with ged4py installed.")
    print("Try: docker-compose exec web python test_import_zielonki.py")
