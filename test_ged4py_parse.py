#!/usr/bin/env python3
"""Test parsing zielonki.ged with ged4py directly."""

import sys
import os

# Add src to path
sys.path.insert(0, 'src')

# Set up minimal Flask app context for imports
os.environ['DATABASE_URL'] = 'postgresql://user:pass@localhost/db'
os.environ['SECRET_KEY'] = 'test'

try:
    from ged4py import GedcomReader
    
    filepath = 'data/zielonki.ged'
    
    print(f"Attempting to parse: {filepath}")
    print()
    
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'ascii']
    
    for encoding in encodings:
        print(f"Testing with encoding: {encoding}")
        try:
            with GedcomReader(filepath, encoding=encoding) as reader:
                count = 0
                for record in reader.records0('INDI'):
                    count += 1
                    if count <= 2:
                        print(f"  Record {count}: {record.xref_id}")
                print(f"  Success! Parsed {count} individuals")
                break
        except Exception as e:
            print(f"  Error: {type(e).__name__}: {e}")
            # Get more details
            import traceback
            print("  Traceback:")
            for line in traceback.format_exc().split('\n'):
                if line.strip():
                    print(f"    {line}")
        print()

except ImportError as e:
    print(f"Cannot import ged4py: {e}")
    print("Try running in the docker container or virtual environment")
