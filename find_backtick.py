#!/usr/bin/env python3
"""Search for backtick characters in zielonki.ged."""

with open('data/zielonki.ged', 'rb') as f:
    content = f.read()

# Search for backtick character (grave accent)
backtick = b'`'  # ASCII 0x60

print("="*70)
print("Searching for backtick (`) characters in zielonki.ged")
print("="*70)
print()

if backtick in content:
    lines = content.split(b'\r\n')
    print('Found backtick characters:')
    print('-'*70)
    
    for i, line in enumerate(lines, 1):
        if backtick in line:
            count = line.count(backtick)
            positions = [pos for pos in range(len(line)) if line[pos:pos+1] == backtick]
            
            print(f'\nLine {i}: {count} backtick(s) found')
            print(f'  Positions: {positions}')
            print(f'  Full line: {line.decode("utf-8", errors="replace")}')
            
            for pos in positions[:5]:
                start = max(0, pos-20)
                end = min(len(line), pos+20)
                context = line[start:end]
                print(f'  Context at position {pos}:')
                print(f'    {context.decode("utf-8", errors="replace")}')
                print(f'    {"~" * (pos-start)}^ here')
else:
    print('No backtick (`) characters found')

print()
print("="*70)
