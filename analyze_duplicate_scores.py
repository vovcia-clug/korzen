#!/usr/bin/env python3
"""
Analyze actual similarity scores for existing Kennedy duplicates
to determine why auto-merge didn't trigger.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import Person
from app.services.duplicate_detector import DuplicateDetector
from sqlalchemy import text

def main():
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("ANALYZING DUPLICATE SIMILARITY SCORES")
        print("=" * 80)
        
        # Get duplicate pairs
        result = db.session.execute(text("""
            SELECT 
                p1.id as id1,
                p2.id as id2,
                p1.first_name,
                p1.last_name,
                p1.birth_date,
                p1.birth_place,
                p1.death_date,
                p1.death_place,
                p2.birth_place as p2_birth_place,
                p2.death_date as p2_death_date,
                p2.death_place as p2_death_place
            FROM persons p1
            JOIN persons p2 ON 
                p1.first_name = p2.first_name 
                AND p1.last_name = p2.last_name 
                AND COALESCE(p1.birth_date, '1900-01-01'::date) = COALESCE(p2.birth_date, '1900-01-01'::date)
                AND p1.id < p2.id
            WHERE p1.last_name LIKE '%Kennedy%'
            LIMIT 5;
        """))
        
        duplicates = result.fetchall()
        
        if not duplicates:
            print("\n✓ No duplicates found!")
            return
        
        print(f"\nFound {len(duplicates)} duplicate pairs. Analyzing scores...\n")
        
        # Initialize duplicate detector
        detector = DuplicateDetector()
        
        for i, dup in enumerate(duplicates, 1):
            print(f"\n{'=' * 80}")
            print(f"DUPLICATE PAIR #{i}")
            print(f"{'=' * 80}")
            
            # Get full person objects
            person1 = Person.query.get(dup[0])
            person2 = Person.query.get(dup[1])
            
            if not person1 or not person2:
                print("  ⚠️  Could not load person objects")
                continue
            
            print(f"\nPerson 1 (ID: {person1.id}):")
            print(f"  Name: {person1.first_name} {person1.last_name}")
            print(f"  Birth: {person1.birth_date} at {person1.birth_place or 'N/A'}")
            print(f"  Death: {person1.death_date or 'N/A'} at {person1.death_place or 'N/A'}")
            print(f"  GEDCOM: {person1.gedcom_id}")
            print(f"  Has embedding: {person1.embedding is not None}")
            
            print(f"\nPerson 2 (ID: {person2.id}):")
            print(f"  Name: {person2.first_name} {person2.last_name}")
            print(f"  Birth: {person2.birth_date} at {person2.birth_place or 'N/A'}")
            print(f"  Death: {person2.death_date or 'N/A'} at {person2.death_place or 'N/A'}")
            print(f"  GEDCOM: {person2.gedcom_id}")
            print(f"  Has embedding: {person2.embedding is not None}")
            
            # Calculate similarity
            try:
                # Check if person2 would be detected as duplicate of person1
                duplicates_found = detector.detect_person_duplicates(person2, limit=10)
                
                # Find person1 in the results
                found_match = False
                for candidate, score, breakdown in duplicates_found:
                    if candidate.id == person1.id:
                        found_match = True
                        print(f"\n📊 SIMILARITY ANALYSIS:")
                        print(f"  Composite Score: {score:.4f} ({score*100:.2f}%)")
                        print(f"  Vector Similarity: {breakdown.get('vector', 0):.4f}")
                        print(f"  Phonetic Similarity: {breakdown.get('phonetic', 0):.4f}")
                        print(f"  Date Similarity: {breakdown.get('date', 0):.4f}")
                        print(f"  Location Similarity: {breakdown.get('location', 0):.4f}")
                        
                        # Check thresholds
                        print(f"\n🎯 THRESHOLD ANALYSIS:")
                        print(f"  DUPLICATE_THRESHOLD (0.85): {'✓ PASS' if score >= 0.85 else '✗ FAIL'}")
                        print(f"  AUTO_MERGE_THRESHOLD (0.95): {'✓ PASS' if score >= 0.95 else '✗ FAIL'}")
                        
                        if score >= 0.85 and score < 0.95:
                            print(f"\n❌ ROOT CAUSE: Score {score:.4f} is in the gap!")
                            print(f"   Detected as duplicate but NOT auto-merged")
                        elif score < 0.85:
                            print(f"\n⚠️  Score {score:.4f} below detection threshold")
                            print(f"   Not even detected as duplicate!")
                        else:
                            print(f"\n✓ Score {score:.4f} should trigger auto-merge")
                        
                        break
                
                if not found_match:
                    print(f"\n❌ Person 1 NOT FOUND in duplicate detection results!")
                    print(f"   This indicates a detection problem, not a threshold problem")
                    if duplicates_found:
                        print(f"\n   Top matches found instead:")
                        for candidate, score, breakdown in duplicates_found[:3]:
                            print(f"     - {candidate.first_name} {candidate.last_name} (Score: {score:.4f})")
                    else:
                        print(f"   No duplicates detected at all!")
                        
            except Exception as e:
                print(f"\n❌ Error calculating similarity: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'=' * 80}")
        print("ANALYSIS COMPLETE")
        print(f"{'=' * 80}")

if __name__ == "__main__":
    main()
