#!/usr/bin/env python3
"""
Diagnose GEDCOM parsing issues in zielonki.ged
"""

def diagnose_gedcom_file(filepath):
    """Analyze GEDCOM file for common parsing issues."""
    
    print("="*70)
    print("GEDCOM FILE DIAGNOSTIC REPORT")
    print("="*70)
    print(f"File: {filepath}")
    print()
    
    with open(filepath, 'rb') as f:
        content = f.read()
    
    # Split by CRLF (Windows line endings)
    lines = content.split(b'\r\n')
    
    print(f"Total lines: {len(lines)}")
    print()
    
    # Check for blank lines (GEDCOM spec doesn't allow blank lines)
    print("ISSUE #1: Blank Lines (Not allowed in GEDCOM)")
    print("-" * 70)
    blank_lines = []
    for i, line in enumerate(lines, 1):
        if not line.strip() and i < len(lines):  # Exclude trailing empty line
            blank_lines.append(i)
            if len(blank_lines) <= 10:  # Show first 10
                prev_line = lines[i-2] if i > 1 else b''
                next_line = lines[i] if i < len(lines) else b''
                print(f"  Line {i}: BLANK")
                print(f"    Previous: {prev_line[:70]}")
                print(f"    Next:     {next_line[:70]}")
                print()
    
    if blank_lines:
        print(f"✗ FOUND {len(blank_lines)} BLANK LINES")
        print(f"  Line numbers: {blank_lines[:20]}")
        if len(blank_lines) > 20:
            print(f"  ... and {len(blank_lines) - 20} more")
        print()
        print("  DIAGNOSIS: ged4py parser rejects blank lines as invalid GEDCOM syntax.")
        print("  The error 'Invalid syntax at line 11' refers to the first blank line.")
        print()
    else:
        print("✓ No blank lines found")
        print()
    
    # Check for lines not starting with level number
    print("ISSUE #2: Lines Not Starting with Level Number")
    print("-" * 70)
    invalid_lines = []
    for i, line in enumerate(lines, 1):
        if line.strip() and not line.strip()[0:1].isdigit():
            invalid_lines.append((i, line[:80]))
            if len(invalid_lines) <= 5:
                print(f"  Line {i}: {line[:80]}")
    
    if invalid_lines:
        print(f"✗ FOUND {len(invalid_lines)} LINES NOT STARTING WITH DIGIT")
    else:
        print("✓ All non-blank lines start with level number")
    print()
    
    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    if blank_lines:
        print("PRIMARY ISSUE: Blank lines in GEDCOM file")
        print(f"  - {len(blank_lines)} blank lines detected")
        print(f"  - First blank line at line {blank_lines[0]}")
        print(f"  - ged4py parser strictly follows GEDCOM spec which prohibits blank lines")
        print()
        print("RECOMMENDED FIX:")
        print("  1. Remove all blank lines from the GEDCOM file")
        print("  2. OR modify the parser to skip blank lines during import")
    else:
        print("✓ No obvious GEDCOM syntax issues found")
    
    print()
    return blank_lines

if __name__ == '__main__':
    blank_lines = diagnose_gedcom_file('data/zielonki.ged')
    
    if blank_lines:
        print()
        print("Would you like to see a preview of the cleaned file? (y/n)")
        print("Or run: python3 fix_blank_lines.py data/zielonki.ged")
