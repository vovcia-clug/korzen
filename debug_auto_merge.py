#!/usr/bin/env python3
"""
Debug script to check auto-merge during GEDCOM parsing.
"""
import sys
import os

# Set up path to import from src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import Person, DuplicateCandidate, DuplicateResolution
from app.gedcom_parser import GedcomParser
from app.gedcom_constants import ENABLE_AUTO_MERGE, AUTO_MERGE_THRESHOLD

# Print configuration
print("\n" + "="*80)
print("AUTO-MERGE CONFIGURATION")
print("="*80)
print(f"ENABLE_AUTO_MERGE: {ENABLE_AUTO_MERGE}")
print(f"AUTO_MERGE_THRESHOLD: {AUTO_MERGE_THRESHOLD}")
print()

# Create Flask app
app = create_app()

with app.app_context():
    # Clear database (delete in correct order to avoid FK constraints)
    print("Clearing database...")
    from app.models import BaptismRecord, DeathRecord, MarriageRecord, GenealogicalRecord, RecordBatch
    DuplicateResolution.query.delete()
    DuplicateCandidate.query.delete()
    BaptismRecord.query.delete()
    DeathRecord.query.delete()
    MarriageRecord.query.delete()
    GenealogicalRecord.query.delete()
    Person.query.delete()
    RecordBatch.query.delete()
    db.session.commit()
    print("✓ Database cleared\n")
    
    # Import baseline data
    print("="*80)
    print("IMPORTING BASELINE DATA (test_duplicates_set1.ged)")
    print("="*80)
    parser = GedcomParser('data/test_duplicates_set1.ged')
    stats1 = parser.parse()
    print(f"\n✓ Baseline import completed:")
    print(f"  - Persons: {stats1['persons']}")
    print(f"  - Duplicate Candidates: {DuplicateCandidate.query.count()}")
    
    # Import data with duplicates
    print("\n" + "="*80)
    print("IMPORTING DUPLICATES (test_duplicates_set2.ged)")
    print("="*80)
    parser2 = GedcomParser('data/test_duplicates_set2.ged')
    stats2 = parser2.parse()
    print(f"\n✓ Duplicate import completed:")
    print(f"  - Total persons: {Person.query.count()}")
    print(f"  - Persons added this import: {stats2['persons']}")
    print(f"  - Duplicate Candidates: {DuplicateCandidate.query.count()}")
    print(f"  - Duplicate Resolutions: {DuplicateResolution.query.count()}")
    
    # Show duplicate candidates
    print("\n" + "="*80)
    print("DUPLICATE CANDIDATES IN DATABASE")
    print("="*80)
    candidates = DuplicateCandidate.query.filter_by(record_type='person').all()
    for c in candidates:
        p1 = Person.query.get(c.record1_id)
        p2 = Person.query.get(c.record2_id)
        print(f"\nStatus: {c.status}, Score: {c.composite_score:.10f}")
        print(f"  Record 1: {p1.first_name} {p1.last_name} (ID: {p1.id})")
        print(f"  Record 2: {p2.first_name} {p2.last_name} (ID: {p2.id})")
        print(f"  Threshold check: {c.composite_score} >= {AUTO_MERGE_THRESHOLD - 0.0001} = {c.composite_score >= AUTO_MERGE_THRESHOLD - 0.0001}")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
