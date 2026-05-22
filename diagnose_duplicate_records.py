#!/usr/bin/env python3
"""
Diagnose the "Record not found" issue on the Duplicates page.
This script checks for orphaned DuplicateCandidate entries where the referenced records no longer exist.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.models import DuplicateCandidate, Person, BaptismRecord, MarriageRecord, DeathRecord
from app.extensions import db
from app import create_app

def diagnose_orphaned_candidates():
    """Check for DuplicateCandidate entries with missing records."""
    
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("DIAGNOSING DUPLICATE CANDIDATES WITH MISSING RECORDS")
        print("=" * 80)
        
        # Get all duplicate candidates
        all_candidates = DuplicateCandidate.query.all()
        print(f"\nTotal duplicate candidates: {len(all_candidates)}")
        
        orphaned_candidates = []
        
        for candidate in all_candidates:
            record1_exists = False
            record2_exists = False
            
            # Check if records exist based on type
            if candidate.record_type == 'person':
                record1_exists = db.session.get(Person, candidate.record1_id) is not None
                record2_exists = db.session.get(Person, candidate.record2_id) is not None
            elif candidate.record_type == 'baptism':
                record1_exists = db.session.get(BaptismRecord, candidate.record1_id) is not None
                record2_exists = db.session.get(BaptismRecord, candidate.record2_id) is not None
            elif candidate.record_type == 'marriage':
                record1_exists = db.session.get(MarriageRecord, candidate.record1_id) is not None
                record2_exists = db.session.get(MarriageRecord, candidate.record2_id) is not None
            elif candidate.record_type == 'death':
                record1_exists = db.session.get(DeathRecord, candidate.record1_id) is not None
                record2_exists = db.session.get(DeathRecord, candidate.record2_id) is not None
            
            # Track orphaned candidates
            if not record1_exists or not record2_exists:
                orphaned_candidates.append({
                    'candidate_id': str(candidate.id),
                    'record_type': candidate.record_type,
                    'record1_id': str(candidate.record1_id),
                    'record1_exists': record1_exists,
                    'record2_id': str(candidate.record2_id),
                    'record2_exists': record2_exists,
                    'status': candidate.status,
                    'composite_score': candidate.composite_score,
                    'detected_at': candidate.detected_at
                })
        
        print(f"\n{'=' * 80}")
        print(f"ORPHANED CANDIDATES (missing one or both records): {len(orphaned_candidates)}")
        print(f"{'=' * 80}\n")
        
        if orphaned_candidates:
            # Group by status
            by_status = {}
            for orphan in orphaned_candidates:
                status = orphan['status']
                if status not in by_status:
                    by_status[status] = []
                by_status[status].append(orphan)
            
            print("Breakdown by status:")
            for status, items in by_status.items():
                print(f"  {status}: {len(items)}")
            
            print("\nFirst 10 orphaned candidates:")
            for i, orphan in enumerate(orphaned_candidates[:10], 1):
                print(f"\n{i}. Candidate ID: {orphan['candidate_id']}")
                print(f"   Type: {orphan['record_type']}")
                print(f"   Status: {orphan['status']}")
                print(f"   Score: {orphan['composite_score']:.3f}")
                print(f"   Record 1: {orphan['record1_id']} - {'EXISTS' if orphan['record1_exists'] else 'MISSING'}")
                print(f"   Record 2: {orphan['record2_id']} - {'EXISTS' if orphan['record2_exists'] else 'MISSING'}")
                print(f"   Detected: {orphan['detected_at']}")
            
            # Provide cleanup recommendation
            print(f"\n{'=' * 80}")
            print("RECOMMENDATION:")
            print("=" * 80)
            print(f"Found {len(orphaned_candidates)} orphaned duplicate candidates.")
            print("These should be cleaned up to prevent 'Record not found' errors.")
            print("\nOptions:")
            print("1. Delete orphaned candidates where both records are missing")
            print("2. Mark orphaned candidates as 'rejected' if one record is missing")
            print("3. Add CASCADE delete constraints to automatically clean up")
            
        else:
            print("✓ No orphaned candidates found! All duplicate candidates reference existing records.")
        
        print(f"\n{'=' * 80}")
        print("DIAGNOSIS COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    diagnose_orphaned_candidates()
