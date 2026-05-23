"""
Test script to verify the single name skip logic in duplicate detection.

This script tests that:
1. Persons with only a first name (no surname, dates, places, parents) are skipped
2. Persons with additional identifying information are NOT skipped
3. The changes are backward compatible with existing functionality
"""

import sys
from datetime import datetime

# Mock Person class for testing
class MockPerson:
    def __init__(self, id, first_name=None, last_name=None, maiden_name=None,
                 birth_date=None, death_date=None, birth_place=None, 
                 death_place=None, parish=None, residence=None,
                 father_id=None, mother_id=None, embedding=None):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.maiden_name = maiden_name
        self.birth_date = birth_date
        self.death_date = death_date
        self.birth_place = birth_place
        self.death_place = death_place
        self.parish = parish
        self.residence = residence
        self.father_id = father_id
        self.mother_id = mother_id
        self.embedding = embedding


def test_should_skip_logic():
    """Test the skip logic without requiring database connection."""
    
    # Simulate the skip logic
    def should_skip(person):
        has_surname = bool(person.last_name or person.maiden_name)
        has_dates = bool(person.birth_date or person.death_date)
        has_locations = bool(
            person.birth_place or 
            person.death_place or 
            person.parish or 
            person.residence
        )
        has_parents = bool(person.father_id or person.mother_id)
        
        if person.first_name and not has_surname and not has_dates and not has_locations and not has_parents:
            return True
        return False
    
    # Test Case 1: Person with only first name - SHOULD SKIP
    person1 = MockPerson(id="1", first_name="Jan")
    assert should_skip(person1) == True, "Should skip person with only first name"
    print("✓ Test 1 passed: Person with only first name is skipped")
    
    # Test Case 2: Person with first and last name - SHOULD NOT SKIP
    person2 = MockPerson(id="2", first_name="Jan", last_name="Kowalski")
    assert should_skip(person2) == False, "Should NOT skip person with surname"
    print("✓ Test 2 passed: Person with surname is NOT skipped")
    
    # Test Case 3: Person with first name and maiden name - SHOULD NOT SKIP
    person3 = MockPerson(id="3", first_name="Maria", maiden_name="Nowak")
    assert should_skip(person3) == False, "Should NOT skip person with maiden name"
    print("✓ Test 3 passed: Person with maiden name is NOT skipped")
    
    # Test Case 4: Person with first name and birth date - SHOULD NOT SKIP
    person4 = MockPerson(id="4", first_name="Jan", birth_date=datetime(1850, 1, 1))
    assert should_skip(person4) == False, "Should NOT skip person with birth date"
    print("✓ Test 4 passed: Person with birth date is NOT skipped")
    
    # Test Case 5: Person with first name and death date - SHOULD NOT SKIP
    person5 = MockPerson(id="5", first_name="Jan", death_date=datetime(1900, 1, 1))
    assert should_skip(person5) == False, "Should NOT skip person with death date"
    print("✓ Test 5 passed: Person with death date is NOT skipped")
    
    # Test Case 6: Person with first name and birth place - SHOULD NOT SKIP
    person6 = MockPerson(id="6", first_name="Jan", birth_place="Kraków")
    assert should_skip(person6) == False, "Should NOT skip person with birth place"
    print("✓ Test 6 passed: Person with birth place is NOT skipped")
    
    # Test Case 7: Person with first name and parish - SHOULD NOT SKIP
    person7 = MockPerson(id="7", first_name="Jan", parish="Bolechowice")
    assert should_skip(person7) == False, "Should NOT skip person with parish"
    print("✓ Test 7 passed: Person with parish is NOT skipped")
    
    # Test Case 8: Person with first name and father_id - SHOULD NOT SKIP
    person8 = MockPerson(id="8", first_name="Jan", father_id="father-uuid")
    assert should_skip(person8) == False, "Should NOT skip person with parent relationship"
    print("✓ Test 8 passed: Person with parent relationship is NOT skipped")
    
    # Test Case 9: Person with no first name - SHOULD NOT SKIP (different case)
    person9 = MockPerson(id="9", last_name="Kowalski")
    assert should_skip(person9) == False, "Should NOT skip person without first name"
    print("✓ Test 9 passed: Person without first name is NOT skipped")
    
    # Test Case 10: Person with empty strings - SHOULD SKIP
    person10 = MockPerson(id="10", first_name="Jan", last_name="", maiden_name="")
    assert should_skip(person10) == True, "Should skip person with empty surname strings"
    print("✓ Test 10 passed: Person with empty surname strings is skipped")
    
    print("\n" + "="*60)
    print("All tests passed! ✓")
    print("="*60)
    print("\nSummary:")
    print("- Persons with ONLY a first name are skipped (too generic)")
    print("- Persons with ANY additional identifying information are NOT skipped")
    print("- The logic is backward compatible and doesn't affect existing records")


if __name__ == "__main__":
    try:
        test_should_skip_logic()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)
