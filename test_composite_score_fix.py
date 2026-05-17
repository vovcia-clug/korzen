#!/usr/bin/env python3
"""
Test to verify the composite score bug fix in save_duplicate_candidate().

This test verifies that:
1. Component scores are stored as None when they should be masked
2. Composite score is calculated correctly with normalization
3. The mathematical impossibility (Composite = 1.0 with all components = 0.0) is resolved
"""

import sys
sys.path.insert(0, 'src')

from app import create_app
from app.extensions import db
from app.models import Person, DuplicateCandidate
from app.services.duplicate_detector import DuplicateDetector
from app.services.embedding_generator import EmbeddingGenerator
from app.services.feature_extractor import FeatureExtractor
from datetime import date

def test_composite_score_fix():
    """Test that composite scores are calculated correctly and None values are preserved."""
    
    app = create_app()
    with app.app_context():
        # Clean up any existing test data (delete resolutions first due to FK constraint)
        from app.models import DuplicateResolution
        db.session.query(DuplicateResolution).delete()
        db.session.query(DuplicateCandidate).delete()
        db.session.query(Person).filter(Person.gedcom_id.like('TEST_%')).delete()
        db.session.commit()
        
        print("=" * 80)
        print("Testing Composite Score Bug Fix")
        print("=" * 80)
        
        # Create test persons with missing data
        embedding_gen = EmbeddingGenerator()
        feature_extractor = FeatureExtractor()
        
        # Person 1: Has birth date and location
        person1 = Person()
        person1.gedcom_id = 'TEST_PERSON_1'
        person1.first_name = 'John'
        person1.last_name = 'Smith'
        person1.birth_date = date(1850, 1, 1)
        person1.birth_place = 'Kraków'
        features1 = feature_extractor.extract_person_features(person1)
        person1.embedding = embedding_gen.generate_person_embedding(features1)
        db.session.add(person1)
        
        # Person 2: Missing birth date and location (only has name)
        person2 = Person()
        person2.gedcom_id = 'TEST_PERSON_2'
        person2.first_name = 'John'
        person2.last_name = 'Smith'
        person2.birth_date = None  # Missing
        person2.birth_place = None  # Missing
        features2 = feature_extractor.extract_person_features(person2)
        person2.embedding = embedding_gen.generate_person_embedding(features2)
        db.session.add(person2)
        
        db.session.commit()
        
        print("\n[Test Setup]")
        print(f"  Person 1: {person1.first_name} {person1.last_name}")
        print(f"    Birth Date: {person1.birth_date}")
        print(f"    Birth Place: {person1.birth_place}")
        print(f"  Person 2: {person2.first_name} {person2.last_name}")
        print(f"    Birth Date: {person2.birth_date}")
        print(f"    Birth Place: {person2.birth_place}")
        
        # Detect duplicates (this will call save_duplicate_candidate)
        detector = DuplicateDetector()
        duplicates = detector.detect_person_duplicates(person1, limit=10)
        
        print(f"\n[Duplicate Detection]")
        print(f"  Found {len(duplicates)} duplicate(s)")
        
        if duplicates:
            candidate_person, composite_score, score_breakdown = duplicates[0]
            print(f"\n[Score Breakdown from detect_person_duplicates]")
            print(f"  Vector similarity: {score_breakdown['vector_sim']}")
            print(f"  Phonetic similarity: {score_breakdown['phonetic_sim']}")
            print(f"  Date similarity: {score_breakdown['date_sim']}")
            print(f"  Location similarity: {score_breakdown['location_sim']}")
            print(f"  Composite score: {composite_score:.3f}")
        
        # Now check what was saved to the database
        saved_candidate = db.session.query(DuplicateCandidate).filter(
            DuplicateCandidate.record_type == 'person',
            db.or_(
                db.and_(
                    DuplicateCandidate.record1_id == person1.id,
                    DuplicateCandidate.record2_id == person2.id
                ),
                db.and_(
                    DuplicateCandidate.record1_id == person2.id,
                    DuplicateCandidate.record2_id == person1.id
                )
            )
        ).first()
        
        print(f"\n[Saved to Database]")
        if saved_candidate:
            print(f"  Vector similarity: {saved_candidate.vector_similarity}")
            print(f"  Phonetic similarity: {saved_candidate.phonetic_similarity}")
            print(f"  Date similarity: {saved_candidate.date_similarity}")
            print(f"  Location similarity: {saved_candidate.location_similarity}")
            print(f"  Composite score: {saved_candidate.composite_score:.3f}")
            
            # Verify the fix
            print(f"\n[Verification]")
            
            # Check 1: None values should be preserved
            if saved_candidate.date_similarity is None:
                print("  ✓ Date similarity correctly stored as None (masked)")
            else:
                print(f"  ✗ Date similarity should be None but is {saved_candidate.date_similarity}")
            
            if saved_candidate.location_similarity is None:
                print("  ✓ Location similarity correctly stored as None (masked)")
            else:
                print(f"  ✗ Location similarity should be None but is {saved_candidate.location_similarity}")
            
            # Check 2: Composite score should match what was calculated
            if duplicates:
                expected_composite = duplicates[0][1]
                if abs(saved_candidate.composite_score - expected_composite) < 0.001:
                    print(f"  ✓ Composite score matches calculated value ({expected_composite:.3f})")
                else:
                    print(f"  ✗ Composite score mismatch: saved={saved_candidate.composite_score:.3f}, expected={expected_composite:.3f}")
            
            # Check 3: Composite score should be reasonable (not 0.0 or incorrectly calculated)
            if saved_candidate.composite_score > 0.5:
                print(f"  ✓ Composite score is reasonable ({saved_candidate.composite_score:.3f} > 0.5)")
            else:
                print(f"  ✗ Composite score is too low: {saved_candidate.composite_score:.3f}")
            
            # Check 4: Mathematical consistency - if all components are 0.0, composite can't be 1.0
            all_zero = (
                saved_candidate.vector_similarity == 0.0 and
                (saved_candidate.phonetic_similarity == 0.0 or saved_candidate.phonetic_similarity is None) and
                (saved_candidate.date_similarity == 0.0 or saved_candidate.date_similarity is None) and
                (saved_candidate.location_similarity == 0.0 or saved_candidate.location_similarity is None)
            )
            if all_zero and saved_candidate.composite_score > 0.5:
                print(f"  ✗ MATHEMATICAL IMPOSSIBILITY: All components ~0.0 but composite={saved_candidate.composite_score:.3f}")
            else:
                print(f"  ✓ No mathematical impossibility detected")
            
        else:
            print("  ✗ No duplicate candidate saved to database!")
        
        # Clean up (delete resolutions first due to FK constraint)
        from app.models import DuplicateResolution
        db.session.query(DuplicateResolution).delete()
        db.session.query(DuplicateCandidate).delete()
        db.session.query(Person).filter(Person.gedcom_id.like('TEST_%')).delete()
        db.session.commit()
        
        print("\n" + "=" * 80)
        print("Test Complete!")
        print("=" * 80)

if __name__ == '__main__':
    test_composite_score_fix()
