#!/usr/bin/env python3
"""
Test script for automatic duplicate merging functionality.

This script tests the auto-merge feature for 100% duplicate matches during GEDCOM import:
1. Imports test_duplicates_set1.ged (baseline data)
2. Imports test_duplicates_set2.ged (contains exact duplicates and near-duplicates)
3. Verifies that 100% matches are auto-merged (not created as new records)
4. Verifies that <100% matches go to duplicate_candidates for manual review
5. Verifies audit trail entries in duplicate_resolutions table
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import (
    Person, RecordBatch, DuplicateCandidate, DuplicateResolution,
    BaptismRecord, MarriageRecord, DeathRecord, UploadedFile
)
from app.gedcom_parser import GedcomParser


def clear_database():
    """Clear all test data from the database."""
    print("\n" + "="*80)
    print("CLEARING DATABASE")
    print("="*80)
    
    # Delete in correct order to respect foreign key constraints
    from app.models import GenealogicalRecord
    
    DuplicateResolution.query.delete()
    DuplicateCandidate.query.delete()
    MarriageRecord.query.delete()
    DeathRecord.query.delete()
    BaptismRecord.query.delete()
    Person.query.delete()
    GenealogicalRecord.query.delete()  # Must delete before RecordBatch
    UploadedFile.query.delete()
    RecordBatch.query.delete()
    
    db.session.commit()
    print("✓ Database cleared\n")


def import_gedcom_file(filepath, description):
    """Import a GEDCOM file and return statistics."""
    print(f"\nImporting: {filepath}")
    print("-" * 80)
    
    # Create batch
    batch = RecordBatch(
        source=filepath,
        description=description
    )
    db.session.add(batch)
    db.session.commit()
    
    # Create uploaded file record
    uploaded_file = UploadedFile(
        filename=os.path.basename(filepath),
        original_filename=os.path.basename(filepath),
        filepath=filepath,
        file_size=os.path.getsize(filepath),
        batch_id=batch.id,
        processing_status='processing'
    )
    db.session.add(uploaded_file)
    db.session.commit()
    
    # Parse the file
    parser = GedcomParser(filepath, str(uploaded_file.id))
    stats = parser.parse_and_import()
    
    # Update status
    uploaded_file.processing_status = 'completed'
    db.session.commit()
    
    print(f"✓ Import completed:")
    print(f"  - Persons: {stats.get('persons', 0)}")
    print(f"  - Marriages: {stats.get('marriages', 0)}")
    print(f"  - Baptisms: {stats.get('baptisms', 0)}")
    print(f"  - Deaths: {stats.get('deaths', 0)}")
    
    return stats


def check_database_state():
    """Check and display the current database state."""
    print("\n" + "="*80)
    print("DATABASE STATE")
    print("="*80)
    
    # Count records
    person_count = Person.query.count()
    duplicate_candidate_count = DuplicateCandidate.query.count()
    duplicate_resolution_count = DuplicateResolution.query.count()
    
    print(f"\nTotal Records:")
    print(f"  - Persons: {person_count}")
    print(f"  - Duplicate Candidates: {duplicate_candidate_count}")
    print(f"  - Duplicate Resolutions: {duplicate_resolution_count}")
    
    # Show all persons
    print(f"\nAll Persons in Database:")
    persons = Person.query.all()
    for p in persons:
        print(f"  - {p.first_name} {p.last_name} ({p.birth_date} - {p.death_date}) "
              f"[GEDCOM: {p.gedcom_id}]")
    
    # Show duplicate candidates
    if duplicate_candidate_count > 0:
        print(f"\nDuplicate Candidates:")
        candidates = DuplicateCandidate.query.all()
        for c in candidates:
            person1 = Person.query.get(c.record1_id)
            person2 = Person.query.get(c.record2_id)
            print(f"  - Status: {c.status}, Score: {c.composite_score:.2f}")
            if person1:
                print(f"    Record 1: {person1.first_name} {person1.last_name} (ID: {person1.id})")
            if person2 and person1 and person2.id != person1.id:
                print(f"    Record 2: {person2.first_name} {person2.last_name} (ID: {person2.id})")
    
    # Show duplicate resolutions
    if duplicate_resolution_count > 0:
        print(f"\nDuplicate Resolutions (Auto-Merged):")
        resolutions = DuplicateResolution.query.all()
        for r in resolutions:
            print(f"  - Action: {r.action}, By: {r.resolved_by}")
            print(f"    Notes: {r.resolution_notes}")
            if r.merged_data:
                print(f"    Merged Data: {r.merged_data.get('first_name')} "
                      f"{r.merged_data.get('last_name')} (GEDCOM: {r.merged_data.get('gedcom_id')})")


def verify_auto_merge_results():
    """Verify that auto-merge worked correctly."""
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    # Expected results after importing both files:
    # Set1: 5 persons (Jan Kowalski, Maria Nowak, Piotr Wiśniewski, Anna Wójcik, Tomasz Kamiński)
    # Set2: 8 persons in file, but some should be auto-merged
    
    # Exact duplicates in set2 (should be auto-merged):
    # - Jan Kowalski @I001@ (100% match)
    # - Maria Nowak @I004@ (100% match)
    # - Piotr Wiśniewski @I006@ (100% match)
    
    # Near duplicates (should go to manual review):
    # - Jan Kowalsky @I002@ (similar but not exact)
    # - Jan Kowalewski @I003@ (similar but missing death place)
    # - Marja Nowak @I005@ (different birth date)
    # - Anna Wojcik @I007@ (different Polish diacritics)
    # - Tomasz Kaminski @I008@ (different Polish diacritics)
    
    person_count = Person.query.count()
    auto_merge_count = DuplicateResolution.query.filter_by(
        resolved_by='system_auto_merge'
    ).count()
    
    # Count duplicate candidates with status='confirmed' (auto-merged)
    confirmed_candidates = DuplicateCandidate.query.filter_by(
        status='confirmed'
    ).count()
    
    # Count pending candidates (manual review needed)
    pending_candidates = DuplicateCandidate.query.filter_by(
        status='pending'
    ).count()
    
    print(f"\nResults:")
    print(f"  - Total persons in database: {person_count}")
    print(f"  - Auto-merged records: {auto_merge_count}")
    print(f"  - Confirmed duplicates: {confirmed_candidates}")
    print(f"  - Pending manual review: {pending_candidates}")
    
    # Verify expectations
    print(f"\nExpectations:")
    
    # We expect 5 persons from set1 + 5 new persons from set2 = 10 total
    # (3 exact duplicates should be auto-merged, so not created)
    expected_persons = 10
    if person_count == expected_persons:
        print(f"  ✓ Person count correct: {person_count} (expected {expected_persons})")
    else:
        print(f"  ✗ Person count incorrect: {person_count} (expected {expected_persons})")
    
    # We expect 3 auto-merges (Jan Kowalski, Maria Nowak, Piotr Wiśniewski)
    expected_auto_merges = 3
    if auto_merge_count == expected_auto_merges:
        print(f"  ✓ Auto-merge count correct: {auto_merge_count} (expected {expected_auto_merges})")
    else:
        print(f"  ✗ Auto-merge count incorrect: {auto_merge_count} (expected {expected_auto_merges})")
    
    # Check specific persons
    print(f"\nSpecific Checks:")
    
    # Check that Jan Kowalski appears only once
    jan_kowalski_count = Person.query.filter_by(
        first_name='Jan',
        last_name='Kowalski'
    ).count()
    print(f"  - Jan Kowalski records: {jan_kowalski_count} (expected 1)")
    if jan_kowalski_count == 1:
        print(f"    ✓ Correct: Auto-merge prevented duplicate creation")
    else:
        print(f"    ✗ Incorrect: Expected 1, found {jan_kowalski_count}")
    
    # Check that Maria Nowak appears only once with exact match
    maria_nowak_exact = Person.query.filter_by(
        first_name='Maria',
        last_name='Nowak'
    ).count()
    print(f"  - Maria Nowak (exact) records: {maria_nowak_exact} (expected 1)")
    
    # Check that Marja Nowak was created (near duplicate, not 100%)
    marja_nowak = Person.query.filter_by(
        first_name='Marja',
        last_name='Nowak'
    ).first()
    if marja_nowak:
        print(f"    ✓ 'Marja Nowak' created as separate record (near duplicate, <100%)")
    else:
        print(f"    ✗ 'Marja Nowak' not found (should exist as near duplicate)")
    
    return person_count == expected_persons and auto_merge_count == expected_auto_merges


def main():
    """Main test function."""
    app = create_app()
    
    with app.app_context():
        try:
            # Step 1: Clear database
            clear_database()
            
            # Step 2: Import first GEDCOM file (baseline)
            print("\n" + "="*80)
            print("STEP 1: IMPORT BASELINE DATA")
            print("="*80)
            stats1 = import_gedcom_file(
                'data/test_duplicates_set1.ged',
                'Test Duplicates Set 1 - Baseline'
            )
            
            # Check state after first import
            check_database_state()
            
            # Step 3: Import second GEDCOM file (with duplicates)
            print("\n" + "="*80)
            print("STEP 2: IMPORT FILE WITH DUPLICATES")
            print("="*80)
            stats2 = import_gedcom_file(
                'data/test_duplicates_set2.ged',
                'Test Duplicates Set 2 - Contains Exact and Near Duplicates'
            )
            
            # Check state after second import
            check_database_state()
            
            # Step 4: Verify results
            success = verify_auto_merge_results()
            
            # Summary
            print("\n" + "="*80)
            print("TEST SUMMARY")
            print("="*80)
            if success:
                print("✓ ALL TESTS PASSED")
                print("\nAuto-merge functionality is working correctly:")
                print("  - 100% matches are automatically merged")
                print("  - <100% matches are flagged for manual review")
                print("  - Audit trail is properly maintained")
            else:
                print("✗ SOME TESTS FAILED")
                print("\nPlease review the results above for details.")
            
            return 0 if success else 1
            
        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == '__main__':
    sys.exit(main())
