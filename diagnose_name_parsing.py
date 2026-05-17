"""
Diagnostic script to understand how ged4py handles NAME tags with SURN sub-records.
"""
from ged4py import GedcomReader
import tempfile
import os

# Test GEDCOM with SURN sub-record
gedcom_with_surn = """0 HEAD
1 SOUR test
1 CHAR UTF-8
0 @I1@ INDI
1 NAME Wincenty /Crapiuski/
2 GIVN Wincenty
2 SURN Crapiuski
0 @I2@ INDI
1 NAME John /Doe/
0 TRLR"""

# Write to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
    f.write(gedcom_with_surn)
    temp_file = f.name

print("="*80)
print("DIAGNOSING NAME PARSING ISSUE")
print("="*80)
print()

# Parse and examine structure
with GedcomReader(temp_file, encoding='utf-8') as reader:
    for indi in reader.records0('INDI'):
        print(f"Individual: {indi.xref_id}")
        print("-" * 40)
        for sub in indi.sub_records:
            if sub.tag == 'NAME':
                print(f"  NAME tag value type: {type(sub.value)}")
                print(f"  NAME tag value: {repr(sub.value)}")
                
                # Show what the current buggy code does
                name = sub.value
                if isinstance(name, tuple):
                    # This is the BUG - it only takes the first element!
                    buggy_result = name[0] if name else None
                    print(f"  BUGGY CODE extracts: {repr(buggy_result)}")
                    print(f"  BUGGY CODE loses surname: {repr(name[1]) if len(name) > 1 else 'N/A'}")
                
                print()
                
                # Show sub-records
                if sub.sub_records:
                    print(f"  NAME sub-records:")
                    for subsub in sub.sub_records:
                        print(f"    - {subsub.tag}: {repr(subsub.value)}")
                    print()

print("="*80)
print("CONCLUSION:")
print("="*80)
print("When GEDCOM has NAME with GIVN/SURN sub-records:")
print("  - ged4py returns NAME.value as a tuple: (given, surname, suffix)")
print("  - Current code only takes tuple[0], LOSING THE SURNAME!")
print()
print("FIX: Extract both tuple[0] and tuple[1] when NAME.value is a tuple")
print("="*80)

# Cleanup
os.unlink(temp_file)
