#!/usr/bin/env python3
"""Check for problematic Unicode characters in GEDCOM file."""

with open('data/zielonki.ged', 'rb') as f:
    content = f.read()

# Look for common Unicode quote characters
unicode_quotes = [
    (b'\xe2\x80\x98', 'LEFT SINGLE QUOTATION MARK U+2018'),
    (b'\xe2\x80\x99', 'RIGHT SINGLE QUOTATION MARK U+2019'),
    (b'\xe2\x80\x9c', 'LEFT DOUBLE QUOTATION MARK U+201C'),
    (b'\xe2\x80\x9d', 'RIGHT DOUBLE QUOTATION MARK U+201D'),
    (b'\xe2\x80\x9a', 'SINGLE LOW-9 QUOTATION MARK U+201A'),
    (b'\xe2\x80\x9e', 'DOUBLE LOW-9 QUOTATION MARK U+201E'),
]

lines = content.split(b'\n')
print(f"Total lines: {len(lines)}")
print("\nChecking first 20 lines for Unicode quote characters:\n")

for i, line in enumerate(lines[:20], 1):
    for quote_bytes, quote_name in unicode_quotes:
        if quote_bytes in line:
            pos = line.find(quote_bytes)
            context = line[max(0, pos-20):pos+20]
            print(f'Line {i}: Found {quote_name} at position {pos}')
            print(f'  Context: {context}')
            print(f'  Full line (first 150 chars): {line[:150]}')
            print()
