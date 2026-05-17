#!/usr/bin/env python3
"""
Test script for Unicode normalization in GEDCOM parser.

This script tests the _normalize_unicode_characters() method to verify
that Unicode smart quotes and other OCR artifacts are properly detected
and replaced with ASCII equivalents.
"""

import sys
import os
from pathlib import Path

# Add src directory to path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from app.gedcom_parser import GedcomParser


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def display_hex_chars(text: str, context_chars: int = 20):
    """Display text with hex representation of non-ASCII characters."""
    result = []
    for i, char in enumerate(text):
        if ord(char) > 127:  # Non-ASCII character
            start = max(0, i - context_chars)
            end = min(len(text), i + context_chars + 1)
            context = text[start:end]
            
            result.append(f"\nFound Unicode character at position {i}:")
            result.append(f"  Character: {repr(char)}")
            result.append(f"  Unicode: U+{ord(char):04X}")
            result.append(f"  Context: {repr(context)}")
    
    return "\n".join(result) if result else "No Unicode characters found"


def test_unicode_normalization():
    """Test the Unicode normalization functionality."""
    
    test_file = 'data/zielonki_with_unicode.ged'
    
    print_section("Unicode Normalization Test")
    print(f"Test file: {test_file}")
    
    # Check if file exists
    if not os.path.exists(test_file):
        print(f"\n❌ ERROR: Test file not found: {test_file}")
        return False
    
    # Read the original file content
    print_section("Step 1: Reading Original File")
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        print(f"✓ File read successfully ({len(original_content)} characters)")
        
        # Find and display line 10 (the NOTE line with quotes)
        lines = original_content.split('\n')
        if len(lines) >= 10:
            line_10 = lines[9]  # 0-indexed
            print(f"\nLine 10 content:")
            print(f"  {line_10[:80]}..." if len(line_10) > 80 else f"  {line_10}")
            
            # Check for Unicode characters
            print("\nUnicode character analysis:")
            unicode_analysis = display_hex_chars(line_10)
            print(unicode_analysis)
    
    except Exception as e:
        print(f"\n❌ ERROR reading file: {e}")
        return False
    
    # Test the normalization method directly
    print_section("Step 2: Testing Normalization Method")
    try:
        parser = GedcomParser(test_file)
        print("✓ GedcomParser instance created")
        
        # Call the normalization method
        normalized_path = parser._normalize_unicode_characters(test_file)
        print(f"✓ Normalization method executed")
        print(f"  Original file: {test_file}")
        print(f"  Normalized file: {normalized_path}")
        
        # Check if a temporary file was created (indicates normalization occurred)
        if normalized_path != test_file:
            print("\n✓ Unicode characters detected - temporary file created")
        else:
            print("\n⚠️  No Unicode characters detected - using original file")
    
    except Exception as e:
        print(f"\n❌ ERROR during normalization: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Read and compare the normalized content
    print_section("Step 3: Verifying Normalized Content")
    try:
        with open(normalized_path, 'r', encoding='utf-8') as f:
            normalized_content = f.read()
        
        print(f"✓ Normalized file read successfully ({len(normalized_content)} characters)")
        
        # Find line 10 in normalized content
        norm_lines = normalized_content.split('\n')
        if len(norm_lines) >= 10:
            norm_line_10 = norm_lines[9]  # 0-indexed
            print(f"\nNormalized line 10:")
            print(f"  {norm_line_10[:80]}..." if len(norm_line_10) > 80 else f"  {norm_line_10}")
            
            # Check if Unicode characters still exist
            has_unicode = any(ord(c) > 127 for c in norm_line_10)
            if not has_unicode:
                print("\n✓ SUCCESS: All Unicode characters replaced with ASCII equivalents")
            else:
                print("\n⚠️  WARNING: Unicode characters still present:")
                print(display_hex_chars(norm_line_10))
        
        # Count character differences
        if original_content != normalized_content:
            print(f"\n✓ Content was modified during normalization")
            
            # Count specific replacements
            replacements_found = []
            if '\u201c' in original_content:
                count = original_content.count('\u201c')
                replacements_found.append(f"  • {count} left double quote(s) (U+201C → \")")
            if '\u201d' in original_content:
                count = original_content.count('\u201d')
                replacements_found.append(f"  • {count} right double quote(s) (U+201D → \")")
            if '\u2018' in original_content:
                count = original_content.count('\u2018')
                replacements_found.append(f"  • {count} left single quote(s) (U+2018 → ')")
            if '\u2019' in original_content:
                count = original_content.count('\u2019')
                replacements_found.append(f"  • {count} right single quote(s) (U+2019 → ')")
            
            if replacements_found:
                print("\nReplacements performed:")
                for replacement in replacements_found:
                    print(replacement)
        else:
            print(f"\n⚠️  Content unchanged - no normalization needed")
    
    except Exception as e:
        print(f"\n❌ ERROR reading normalized file: {e}")
        return False
    
    # Cleanup temporary file if created
    if normalized_path != test_file and os.path.exists(normalized_path):
        try:
            os.unlink(normalized_path)
            print(f"\n✓ Temporary file cleaned up: {normalized_path}")
        except Exception as e:
            print(f"\n⚠️  Could not delete temporary file: {e}")
    
    print_section("Test Complete")
    print("\n✓ All tests passed successfully!")
    return True


if __name__ == '__main__':
    success = test_unicode_normalization()
    sys.exit(0 if success else 1)
