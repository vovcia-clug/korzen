#!/usr/bin/env python3
"""Debug line 11 of zielonki.ged file."""

with open('data/zielonki.ged', 'rb') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print("\nLines 9-13 in detail:\n")

for i in range(8, min(13, len(lines))):
    line = lines[i]
    line_num = i + 1
    print(f"Line {line_num}:")
    print(f"  Raw bytes: {line}")
    print(f"  Hex: {line.hex()}")
    print(f"  Length: {len(line)} bytes")
    try:
        decoded = line.decode('utf-8')
        print(f"  UTF-8 decoded: {repr(decoded)}")
    except Exception as e:
        print(f"  UTF-8 decode error: {e}")
    
    # Check each byte
    problematic = []
    for j, byte in enumerate(line):
        if byte > 127:  # Non-ASCII
            problematic.append((j, byte, hex(byte)))
    
    if problematic:
        print(f"  Non-ASCII bytes: {problematic}")
    print()
