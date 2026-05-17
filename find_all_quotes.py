#!/usr/bin/env python3
"""Find all quote characters in GEDCOM file."""

with open('data/zielonki.ged', 'rb') as f:
    lines = f.readlines()

# Look for problematic quote characters
unicode_quotes = {
    b'\xe2\x80\x98': "'",  # U+2018 LEFT SINGLE QUOTATION MARK
    b'\xe2\x80\x99': "'",  # U+2019 RIGHT SINGLE QUOTATION MARK
    b'\xe2\x80\x9c': '"',  # U+201C LEFT DOUBLE QUOTATION MARK
    b'\xe2\x80\x9d': '"',  # U+201D RIGHT DOUBLE QUOTATION MARK
}

print("Searching for Unicode quote characters in zielonki.ged...")
print()

found_count = 0
for line_num, line in enumerate(lines, 1):
    for quote_bytes, replacement in unicode_quotes.items():
        if quote_bytes in line:
            found_count += 1
            # Show position
            pos = 0
            while True:
                pos = line.find(quote_bytes, pos)
                if pos == -1:
                    break
                # Get context around the quote
                start = max(0, pos - 30)
                end = min(len(line), pos + 30)
                context = line[start:end]
                
                print(f"Line {line_num}, position {pos}:")
                print(f"  Found: {quote_bytes.hex()} ({repr(quote_bytes.decode('utf-8'))})")
                print(f"  Context: {context}")
                print(f"  Full line (first 100 bytes): {line[:100]}")
                print()
                
                pos += len(quote_bytes)

if found_count == 0:
    print("No Unicode quote characters found!")
else:
    print(f"\nTotal occurrences: {found_count}")
