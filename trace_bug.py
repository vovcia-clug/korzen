#!/usr/bin/env python3
"""
Trace through the missing data masking bug with concrete Kennedy records.
"""

import sys
sys.path.insert(0, 'src')

from app import create_app
from app.models import Person
from app.services.duplicate_detector import DuplicateDetector

app = create_app()

with app.app_context():
    # Get two identical Kennedy records
    kennedys = Person.query.filter(
        Person.last_name.like('%Kennedy%'),
        Person.first_name.isnot(None)
    ).limit(2).all()
    
    if len(kennedys) < 2:
        print("ERROR: Need at least 2 Kennedy records")
        sys.exit(1)
    
    person1 = kennedys[0]
    person2 = kennedys[1]
    
    print("=" * 80)
    print("TRACING MISSING DATA MASKING BUG")
    print("=" * 80)
    
    print(f"\nPerson 1 (ID: {person1.id}):")
    print(f"  Name: {person1.first_name} {person1.last_name}")
    print(f"  Maiden: {person1.maiden_name}")
    print(f"  Birth Date: {person1.birth_date}")
    print(f"  Death Date: {person1.death_date}")
    print(f"  Birth Place: {person1.birth_place}")
    print(f"  Death Place: {person1.death_place}")
    print(f"  Parish: {person1.parish}")
    print(f"  Residence: {person1.residence}")
    
    print(f"\nPerson 2 (ID: {person2.id}):")
    print(f"  Name: {person2.first_name} {person2.last_name}")
    print(f"  Maiden: {person2.maiden_name}")
    print(f"  Birth Date: {person2.birth_date}")
    print(f"  Death Date: {person2.death_date}")
    print(f"  Birth Place: {person2.birth_place}")
    print(f"  Death Place: {person2.death_place}")
    print(f"  Parish: {person2.parish}")
    print(f"  Residence: {person2.residence}")
    
    # Create detector
    detector = DuplicateDetector()
    
    print("\n" + "=" * 80)
    print("STEP 1: Check helper methods")
    print("=" * 80)
    
    has_names = detector._both_have_names(person1, person2, 'person')
    print(f"\n_both_have_names() returned: {has_names}")
    print(f"  Person1 has name: {bool(person1.first_name or person1.last_name or person1.maiden_name)}")
    print(f"  Person2 has name: {bool(person2.first_name or person2.last_name or person2.maiden_name)}")
    
    has_dates = detector._both_have_dates(person1, person2, 'person')
    print(f"\n_both_have_dates() returned: {has_dates}")
    print(f"  Person1 has date: {bool(person1.birth_date or person1.death_date)}")
    print(f"  Person2 has date: {bool(person2.birth_date or person2.death_date)}")
    
    has_locations = detector._both_have_locations(person1, person2, 'person')
    print(f"\n_both_have_locations() returned: {has_locations}")
    print(f"  Person1 has location: {bool(person1.birth_place or person1.death_place or person1.parish or person1.residence)}")
    print(f"  Person2 has location: {bool(person2.birth_place or person2.death_place or person2.parish or person2.residence)}")
    
    print("\n" + "=" * 80)
    print("STEP 2: Check similarity calculation methods")
    print("=" * 80)
    
    phonetic_sim = detector._calculate_phonetic_similarity_for_record(person1, person2, 'person')
    print(f"\n_calculate_phonetic_similarity_for_record() returned: {phonetic_sim}")
    
    date_sim = detector._calculate_date_similarity_for_record(person1, person2, 'person')
    print(f"_calculate_date_similarity_for_record() returned: {date_sim}")
    
    location_sim = detector._calculate_location_similarity_for_record(person1, person2, 'person')
    print(f"_calculate_location_similarity_for_record() returned: {location_sim}")
    
    print("\n" + "=" * 80)
    print("STEP 3: Calculate composite score")
    print("=" * 80)
    
    # Assume vector similarity of 0.95 for identical records
    vector_sim = 0.95
    
    print(f"\nVector similarity (assumed): {vector_sim}")
    print(f"\nWeights:")
    print(f"  WEIGHT_VECTOR: {detector.WEIGHT_VECTOR}")
    print(f"  WEIGHT_PHONETIC: {detector.WEIGHT_PHONETIC}")
    print(f"  WEIGHT_DATE: {detector.WEIGHT_DATE}")
    print(f"  WEIGHT_LOCATION: {detector.WEIGHT_LOCATION}")
    
    # Manual calculation
    print(f"\nManual calculation:")
    total_weight = 0.0
    composite_score = 0.0
    
    # Vector always included
    composite_score += detector.WEIGHT_VECTOR * vector_sim
    total_weight += detector.WEIGHT_VECTOR
    print(f"  After vector: score={composite_score:.4f}, weight={total_weight:.4f}")
    
    # Phonetic
    if phonetic_sim is not None:
        composite_score += detector.WEIGHT_PHONETIC * phonetic_sim
        total_weight += detector.WEIGHT_PHONETIC
        print(f"  After phonetic: score={composite_score:.4f}, weight={total_weight:.4f}")
    else:
        print(f"  Phonetic SKIPPED (None)")
    
    # Date
    if date_sim is not None:
        composite_score += detector.WEIGHT_DATE * date_sim
        total_weight += detector.WEIGHT_DATE
        print(f"  After date: score={composite_score:.4f}, weight={total_weight:.4f}")
    else:
        print(f"  Date SKIPPED (None)")
    
    # Location
    if location_sim is not None:
        composite_score += detector.WEIGHT_LOCATION * location_sim
        total_weight += detector.WEIGHT_LOCATION
        print(f"  After location: score={composite_score:.4f}, weight={total_weight:.4f}")
    else:
        print(f"  Location SKIPPED (None)")
    
    # Normalize
    if total_weight > 0:
        composite_score = composite_score / total_weight
    
    print(f"\nFinal composite score: {composite_score:.4f}")
    
    print("\n" + "=" * 80)
    print("STEP 4: Call actual calculate_composite_score()")
    print("=" * 80)
    
    actual_composite, breakdown = detector.calculate_composite_score(
        person1, person2, vector_sim, 'person'
    )
    
    print(f"\nActual composite score: {actual_composite:.4f}")
    print(f"Score breakdown:")
    print(f"  vector_sim: {breakdown['vector_sim']}")
    print(f"  phonetic_sim: {breakdown['phonetic_sim']}")
    print(f"  date_sim: {breakdown['date_sim']}")
    print(f"  location_sim: {breakdown['location_sim']}")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    
    if breakdown['phonetic_sim'] == 0.0 and phonetic_sim is not None:
        print("\n❌ BUG FOUND: phonetic_sim is 0.0 but should be", phonetic_sim)
    if breakdown['date_sim'] == 0.0 and date_sim is not None:
        print("❌ BUG FOUND: date_sim is 0.0 but should be", date_sim)
    if breakdown['location_sim'] == 0.0 and location_sim is not None:
        print("❌ BUG FOUND: location_sim is 0.0 but should be", location_sim)
    
    if actual_composite == 1.0 and (phonetic_sim == 0.0 or date_sim == 0.0 or location_sim == 0.0):
        print("\n❌ BUG FOUND: Composite is 1.0 but component scores are 0.0")
        print("   This suggests the breakdown is storing the wrong values!")
