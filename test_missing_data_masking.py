"""
Test script to verify missing data masking implementation in duplicate detection.

This script tests that records with identical core data but missing optional fields
are correctly detected as duplicates with high similarity scores.
"""

import sys
from datetime import datetime
from unittest.mock import Mock

# Mock the database and models
sys.path.insert(0, 'src')

# Create mock Person records for testing
def create_mock_person(first_name, last_name, birth_date=None, death_date=None, 
                       birth_place=None, death_place=None, parish=None):
    """Create a mock Person record with specified attributes."""
    person = Mock()
    person.first_name = first_name
    person.last_name = last_name
    person.maiden_name = None
    person.birth_date = birth_date
    person.death_date = death_date
    person.birth_place = birth_place
    person.death_place = death_place
    person.parish = parish
    person.residence = None
    return person

def test_missing_data_masking():
    """Test that missing data masking works correctly."""
    from app.services.duplicate_detector import DuplicateDetector
    
    detector = DuplicateDetector(threshold=0.85)
    
    print("=" * 80)
    print("Testing Missing Data Masking in Duplicate Detection")
    print("=" * 80)
    
    # Test Case 1: Both records have complete data
    print("\n[Test 1] Both records with complete data:")
    person1 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=datetime(1920, 1, 1),
        birth_place="Kraków",
        parish="St. Mary's"
    )
    person2 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=datetime(1920, 1, 1),
        birth_place="Kraków",
        parish="St. Mary's"
    )
    
    score, breakdown = detector.calculate_composite_score(person1, person2, 0.95, 'person')
    print(f"  Vector similarity: 0.95")
    print(f"  Phonetic similarity: {breakdown['phonetic_sim']}")
    print(f"  Date similarity: {breakdown['date_sim']}")
    print(f"  Location similarity: {breakdown['location_sim']}")
    print(f"  Composite score: {score:.3f}")
    print(f"  ✓ All components used" if all(v is not None for v in [breakdown['phonetic_sim'], breakdown['date_sim'], breakdown['location_sim']]) else "  ✗ Some components missing")
    
    # Test Case 2: One record missing location data
    print("\n[Test 2] Record 2 missing location data (should still be high similarity):")
    person3 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=datetime(1920, 1, 1),
        birth_place="Kraków",
        parish="St. Mary's"
    )
    person4 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=datetime(1920, 1, 1),
        birth_place=None,  # Missing location
        parish=None
    )
    
    score, breakdown = detector.calculate_composite_score(person3, person4, 0.95, 'person')
    print(f"  Vector similarity: 0.95")
    print(f"  Phonetic similarity: {breakdown['phonetic_sim']}")
    print(f"  Date similarity: {breakdown['date_sim']}")
    print(f"  Location similarity: {breakdown['location_sim']}")
    print(f"  Composite score: {score:.3f}")
    print(f"  ✓ Location excluded from calculation" if breakdown['location_sim'] is None else "  ✗ Location should be None")
    print(f"  ✓ Score >= 0.95" if score >= 0.95 else f"  ✗ Score too low (expected >= 0.95, got {score:.3f})")
    
    # Test Case 3: Both records missing location data
    print("\n[Test 3] Both records missing location data (should be high similarity):")
    person5 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=datetime(1920, 1, 1),
        birth_place=None,
        parish=None
    )
    person6 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=datetime(1920, 1, 1),
        birth_place=None,
        parish=None
    )
    
    score, breakdown = detector.calculate_composite_score(person5, person6, 0.95, 'person')
    print(f"  Vector similarity: 0.95")
    print(f"  Phonetic similarity: {breakdown['phonetic_sim']}")
    print(f"  Date similarity: {breakdown['date_sim']}")
    print(f"  Location similarity: {breakdown['location_sim']}")
    print(f"  Composite score: {score:.3f}")
    print(f"  ✓ Location excluded from calculation" if breakdown['location_sim'] is None else "  ✗ Location should be None")
    print(f"  ✓ Score >= 0.95" if score >= 0.95 else f"  ✗ Score too low (expected >= 0.95, got {score:.3f})")
    
    # Test Case 4: One record missing death date
    print("\n[Test 4] Record 2 missing death date (should still be high similarity):")
    person7 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=datetime(1920, 1, 1),
        parish="St. Mary's"
    )
    person8 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=datetime(1850, 1, 1),
        death_date=None,  # Missing death date
        parish="St. Mary's"
    )
    
    score, breakdown = detector.calculate_composite_score(person7, person8, 0.95, 'person')
    print(f"  Vector similarity: 0.95")
    print(f"  Phonetic similarity: {breakdown['phonetic_sim']}")
    print(f"  Date similarity: {breakdown['date_sim']}")
    print(f"  Location similarity: {breakdown['location_sim']}")
    print(f"  Composite score: {score:.3f}")
    print(f"  ✓ Date still included (birth date present)" if breakdown['date_sim'] is not None else "  ✗ Date should be included")
    print(f"  ✓ Score >= 0.90" if score >= 0.90 else f"  ✗ Score too low (expected >= 0.90, got {score:.3f})")
    
    # Test Case 5: Both records missing all dates
    print("\n[Test 5] Both records missing all dates (should exclude date component):")
    person9 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=None,
        death_date=None,
        parish="St. Mary's"
    )
    person10 = create_mock_person(
        "Jan", "Kowalski",
        birth_date=None,
        death_date=None,
        parish="St. Mary's"
    )
    
    score, breakdown = detector.calculate_composite_score(person9, person10, 0.95, 'person')
    print(f"  Vector similarity: 0.95")
    print(f"  Phonetic similarity: {breakdown['phonetic_sim']}")
    print(f"  Date similarity: {breakdown['date_sim']}")
    print(f"  Location similarity: {breakdown['location_sim']}")
    print(f"  Composite score: {score:.3f}")
    print(f"  ✓ Date excluded from calculation" if breakdown['date_sim'] is None else "  ✗ Date should be None")
    print(f"  ✓ Score >= 0.95" if score >= 0.95 else f"  ✗ Score too low (expected >= 0.95, got {score:.3f})")
    
    print("\n" + "=" * 80)
    print("Testing Complete!")
    print("=" * 80)

if __name__ == "__main__":
    test_missing_data_masking()
