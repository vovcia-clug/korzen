"""
Test script for entity counting in GEDCOM files.

This script tests the enhanced count_gedcom_records() function
to ensure it correctly counts all entity types.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.services.gedcom_generator import GedcomGenerator
from src.services.openrouter_client import OpenRouterClient


def test_entity_counting():
    """Test counting of all entity types in GEDCOM content."""
    print("=" * 60)
    print("Entity Counting Test")
    print("=" * 60)
    
    # Sample GEDCOM content with various entity types
    sample_gedcom = """0 HEAD
1 SOUR Test
1 GEDC
2 VERS 5.5.1
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 BIRT
2 DATE 1 JAN 1900
1 BAPM
2 DATE 15 JAN 1900
2 PLAC St. Mary's Church
1 DEAT
2 DATE 31 DEC 1980
0 @I2@ INDI
1 NAME Jane /Smith/
1 SEX F
1 BIRT
2 DATE 5 MAR 1905
1 CHR
2 DATE 20 MAR 1905
2 PLAC Holy Trinity Church
0 @I3@ INDI
1 NAME Robert /Doe/
1 SEX M
1 BIRT
2 DATE 10 JUN 1925
1 DEAT
2 DATE 15 AUG 2000
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 MARR
2 DATE 14 FEB 1924
2 PLAC Warsaw, Poland
1 CHIL @I3@
0 @F2@ FAM
1 HUSB @I3@
1 MARR
2 DATE 5 JUL 1950
0 TRLR
"""
    
    # Create a GedcomGenerator instance (we only need the counting method)
    # We'll pass None for openrouter_client since we're not generating
    generator = GedcomGenerator(openrouter_client=None)
    
    # Count entities
    print("\nCounting entities in sample GEDCOM...")
    counts = generator.count_gedcom_records(sample_gedcom)
    
    print("\n" + "=" * 60)
    print("Entity Counts:")
    print("=" * 60)
    print(f"Total Persons:       {counts['total_persons']}")
    print(f"Individuals (INDI):  {counts['individuals']}")
    print(f"Families (FAM):      {counts['families']}")
    print(f"Baptisms (BAPM/CHR): {counts['baptisms']}")
    print(f"Deaths (DEAT):       {counts['deaths']}")
    print(f"Marriages (MARR):    {counts['marriages']}")
    print(f"Total Events:        {counts['total_events']}")
    print("=" * 60)
    
    # Verify expected counts
    expected = {
        "total_persons": 3,
        "individuals": 3,
        "families": 2,
        "baptisms": 2,  # 1 BAPM + 1 CHR
        "deaths": 2,
        "marriages": 2,
        "total_events": 6  # 2 baptisms + 2 deaths + 2 marriages
    }
    
    print("\nVerifying counts...")
    all_correct = True
    for key, expected_value in expected.items():
        actual_value = counts[key]
        status = "✓" if actual_value == expected_value else "✗"
        print(f"{status} {key}: expected {expected_value}, got {actual_value}")
        if actual_value != expected_value:
            all_correct = False
    
    print("\n" + "=" * 60)
    if all_correct:
        print("✓ All entity counts are correct!")
    else:
        print("✗ Some entity counts are incorrect!")
    print("=" * 60)
    
    return all_correct


def test_empty_gedcom():
    """Test counting with minimal GEDCOM (no entities)."""
    print("\n" + "=" * 60)
    print("Empty GEDCOM Test")
    print("=" * 60)
    
    empty_gedcom = """0 HEAD
1 SOUR Test
0 TRLR
"""
    
    generator = GedcomGenerator(openrouter_client=None)
    counts = generator.count_gedcom_records(empty_gedcom)
    
    print("\nCounts for empty GEDCOM:")
    for key, value in counts.items():
        print(f"  {key}: {value}")
    
    # All counts should be 0
    all_zero = all(value == 0 for value in counts.values())
    
    if all_zero:
        print("\n✓ Empty GEDCOM correctly returns all zeros")
    else:
        print("\n✗ Empty GEDCOM should return all zeros")
    
    return all_zero


def test_complex_gedcom():
    """Test counting with more complex GEDCOM."""
    print("\n" + "=" * 60)
    print("Complex GEDCOM Test")
    print("=" * 60)
    
    complex_gedcom = """0 HEAD
1 SOUR Test
0 @I1@ INDI
1 NAME Person /One/
1 BAPM
2 DATE 1900
0 @I2@ INDI
1 NAME Person /Two/
1 CHR
2 DATE 1901
1 DEAT
2 DATE 1950
0 @I3@ INDI
1 NAME Person /Three/
1 DEAT
2 DATE 1960
0 @I4@ INDI
1 NAME Person /Four/
0 @I5@ INDI
1 NAME Person /Five/
1 BAPM
2 DATE 1905
1 DEAT
2 DATE 1970
0 @F1@ FAM
1 MARR
2 DATE 1920
0 @F2@ FAM
1 MARR
2 DATE 1925
0 @F3@ FAM
1 MARR
2 DATE 1930
0 TRLR
"""
    
    generator = GedcomGenerator(openrouter_client=None)
    counts = generator.count_gedcom_records(complex_gedcom)
    
    print("\nCounts for complex GEDCOM:")
    print(f"  Individuals: {counts['individuals']} (expected: 5)")
    print(f"  Families: {counts['families']} (expected: 3)")
    print(f"  Baptisms: {counts['baptisms']} (expected: 3)")
    print(f"  Deaths: {counts['deaths']} (expected: 3)")
    print(f"  Marriages: {counts['marriages']} (expected: 3)")
    print(f"  Total Events: {counts['total_events']} (expected: 9)")
    
    expected = {
        "individuals": 5,
        "families": 3,
        "baptisms": 3,
        "deaths": 3,
        "marriages": 3,
        "total_events": 9
    }
    
    all_correct = all(counts[key] == expected[key] for key in expected)
    
    if all_correct:
        print("\n✓ Complex GEDCOM counts are correct!")
    else:
        print("\n✗ Some counts are incorrect!")
    
    return all_correct


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("GEDCOM Entity Counting Test Suite")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Basic Entity Counting", test_entity_counting()))
    results.append(("Empty GEDCOM", test_empty_gedcom()))
    results.append(("Complex GEDCOM", test_complex_gedcom()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
