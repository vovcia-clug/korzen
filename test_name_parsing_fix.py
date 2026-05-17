"""
Test script to verify the surname parsing fix.
"""
from src.app.utils.name_parser import NameParser

print("="*80)
print("TESTING NAME PARSER FIX")
print("="*80)
print()

# Test cases
test_cases = [
    {
        'name': 'Test 1: Tuple with GIVN/SURN (the bug case)',
        'input': ('Wincenty', 'Crapiuski', ''),
        'expected': ('Wincenty', 'Crapiuski')
    },
    {
        'name': 'Test 2: Tuple with both names',
        'input': ('John', 'Doe', ''),
        'expected': ('John', 'Doe')
    },
    {
        'name': 'Test 3: Tuple with only given name',
        'input': ('Mary',),
        'expected': ('Mary', None)
    },
    {
        'name': 'Test 4: String with slashes (traditional GEDCOM)',
        'input': 'Jan /Kowalski/',
        'expected': ('Jan', 'Kowalski')
    },
    {
        'name': 'Test 5: String without slashes',
        'input': 'Anna Nowak',
        'expected': ('Anna', 'Nowak')
    },
    {
        'name': 'Test 6: String with only first name',
        'input': 'Peter',
        'expected': ('Peter', None)
    },
    {
        'name': 'Test 7: Empty string',
        'input': '',
        'expected': (None, None)
    },
    {
        'name': 'Test 8: None',
        'input': None,
        'expected': (None, None)
    },
    {
        'name': 'Test 9: Tuple with empty surname',
        'input': ('Catherine', '', ''),
        'expected': ('Catherine', None)
    },
    {
        'name': 'Test 10: Complex name with slashes',
        'input': 'Maria Teresa /von Habsburg/',
        'expected': ('Maria Teresa', 'von Habsburg')
    },
]

passed = 0
failed = 0

for test in test_cases:
    result = NameParser.extract_name_parts(test['input'])
    expected = test['expected']
    
    if result == expected:
        print(f"✓ {test['name']}")
        print(f"  Input: {repr(test['input'])}")
        print(f"  Result: {result}")
        passed += 1
    else:
        print(f"✗ {test['name']}")
        print(f"  Input: {repr(test['input'])}")
        print(f"  Expected: {expected}")
        print(f"  Got: {result}")
        failed += 1
    print()

print("="*80)
print(f"RESULTS: {passed} passed, {failed} failed")
print("="*80)

if failed == 0:
    print("✓ ALL TESTS PASSED! The surname parsing bug is FIXED!")
else:
    print(f"✗ {failed} test(s) failed. Please review.")
