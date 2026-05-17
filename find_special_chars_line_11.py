#!/usr/bin/env python3
"""Find the actual problematic character on or around line 11."""

with open('data/zielonki.ged', 'rb') as f:
    content = f.read()

# Split by different line endings to understand structure
lines_crlf = content.split(b'\r\n')

print("="*70)
print("Analyzing line 11 and surrounding area")
print("="*70)
print()

print("Lines 8-13 with detailed byte analysis:")
print("-"*70)
for i in range(7, min(13, len(lines_crlf))):
    line = lines_crlf[i]
    print(f"\nLine {i+1}:")
    print(f"  Hex: {line.hex()}")
    print(f"  Repr: {repr(line)}")
    print(f"  Decoded: {line.decode('utf-8', errors='replace')[:100]}")
    
    # Check each byte
    special_bytes = []
    for j, byte in enumerate(line):
        if byte > 127 or (byte < 32 and byte not in (9, 10, 13)):
            special_bytes.append((j, byte, hex(byte)))
    
    if special_bytes:
        print(f"  Special bytes found:")
        for pos, byte, hexval in special_bytes:
            context_start = max(0, pos-10)
            context_end = min(len(line), pos+15)
            context = line[context_start:context_end]
            print(f"    Position {pos}: byte {hexval} ({byte}) - context: {context}")

print("\n" + "="*70)
print("Looking for specific quote-like characters:")
print("-"*70)

# Check for specific characters
quote_chars = [
    (b'\xe2\x80\x98', "U+2018 LEFT SINGLE QUOTATION MARK"),
    (b'\xe2\x80\x99', "U+2019 RIGHT SINGLE QUOTATION MARK"),
    (b'\xe2\x80\x9c', 'U+201C LEFT DOUBLE QUOTATION MARK'),
    (b'\xe2\x80\x9d', 'U+201D RIGHT DOUBLE QUOTATION MARK'),
    (b'\xc2\xb4', 'U+00B4 ACUTE ACCENT'),
    (b'\x60', 'U+0060 GRAVE ACCENT (backtick)'),
    (b'\x27', "U+0027 APOSTROPHE"),
    (b'"', 'U+0022 QUOTATION MARK'),
]

for i in range(7, min(15, len(lines_crlf))):
    line = lines_crlf[i]
    for char_bytes, description in quote_chars:
        if char_bytes in line:
            count = line.count(char_bytes)
            print(f"\nLine {i+1}: Found {count}x {description}")
            print(f"  Full line: {line.decode('utf-8', errors='replace')[:150]}")
