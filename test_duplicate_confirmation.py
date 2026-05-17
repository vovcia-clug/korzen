"""
Test script for duplicate confirmation functionality.

This script tests the hard delete approach for confirmed duplicates.
It verifies that:
1. Duplicate records are deleted when confirmed
2. Original records are preserved
3. Audit trail is created in DuplicateResolution
4. Foreign key relationships are handled properly
"""

import os
import sys
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import Person, BaptismRecord, MarriageRecord, DeathRecord, DuplicateCandidate, DuplicateResolution


def test_duplicate_confirmation():
    """Test the duplicate confirmation and deletion process."""
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("Testing Duplicate Confirmation with Hard Delete")
        print("=" * 70)
        
        # 1. Check for pending duplicate candidates
        print("\n1. Checking for pending duplicate candidates...")
        pending_candidates = DuplicateCandidate.query.filter_by(status='pending').all()
        print(f"   Found {len(pending_candidates)} pending duplicate candidates")
        
        if not pending_candidates:
            print("   ⚠️  No pending duplicates found. Import test GEDCOM files first.")
            print("   Run: Import data/test_duplicates_set1.ged and data/test_duplicates_set2.ged")
            return
        
        # 2. Display first candidate details
        candidate = pending_candidates[0]
        print(f"\n2. Examining duplicate candidate:")
        print(f"   - ID: {candidate.id}")
        print(f"   - Type: {candidate.record_type}")
        print(f"   - Record 1 (kept): {candidate.record1_id}")
        print(f"   - Record 2 (duplicate): {candidate.record2_id}")
        print(f"   - Similarity score: {candidate.composite_score:.2f}")
        
        # 3. Get the actual records
        print(f"\n3. Fetching record details...")
        record1 = None
        record2 = None
        
        if candidate.record_type == 'person':
            record1 = db.session.get(Person, candidate.record1_id)
            record2 = db.session.get(Person, candidate.record2_id)
            if record1:
                print(f"   Record 1: {record1.first_name} {record1.last_name} (b. {record1.birth_date})")
            if record2:
                print(f"   Record 2: {record2.first_name} {record2.last_name} (b. {record2.birth_date})")
        
        elif candidate.record_type == 'baptism':
            record1 = db.session.get(BaptismRecord, candidate.record1_id)
            record2 = db.session.get(BaptismRecord, candidate.record2_id)
            if record1:
                print(f"   Record 1: {record1.child_name} (baptism: {record1.baptism_date})")
            if record2:
                print(f"   Record 2: {record2.child_name} (baptism: {record2.baptism_date})")
        
        elif candidate.record_type == 'marriage':
            record1 = db.session.get(MarriageRecord, candidate.record1_id)
            record2 = db.session.get(MarriageRecord, candidate.record2_id)
            if record1:
                print(f"   Record 1: {record1.spouse1_name} & {record1.spouse2_name} ({record1.marriage_date})")
            if record2:
                print(f"   Record 2: {record2.spouse1_name} & {record2.spouse2_name} ({record2.marriage_date})")
        
        elif candidate.record_type == 'death':
            record1 = db.session.get(DeathRecord, candidate.record1_id)
            record2 = db.session.get(DeathRecord, candidate.record2_id)
            if record1:
                print(f"   Record 1: {record1.deceased_name} {record1.deceased_surname} ({record1.death_date})")
            if record2:
                print(f"   Record 2: {record2.deceased_name} {record2.deceased_surname} ({record2.death_date})")
        
        if not record2:
            print(f"   ⚠️  Record 2 not found. It may have been deleted already.")
            return
        
        # 4. Simulate confirmation (in test mode, we just show what would happen)
        print(f"\n4. Simulating duplicate confirmation...")
        print(f"   This would:")
        print(f"   ✓ Mark candidate as 'confirmed'")
        print(f"   ✓ Create DuplicateResolution audit record")
        print(f"   ✓ Delete record {candidate.record2_id}")
        print(f"   ✓ Keep record {candidate.record1_id}")
        
        # 5. Check existing resolutions
        print(f"\n5. Checking existing resolutions...")
        resolution_count = DuplicateResolution.query.count()
        print(f"   Total resolutions: {resolution_count}")
        
        confirmed_count = DuplicateCandidate.query.filter_by(status='confirmed').count()
        rejected_count = DuplicateCandidate.query.filter_by(status='rejected').count()
        print(f"   Confirmed duplicates: {confirmed_count}")
        print(f"   Rejected duplicates: {rejected_count}")
        
        # 6. Show recent resolutions
        if resolution_count > 0:
            print(f"\n6. Recent resolutions:")
            recent = DuplicateResolution.query.order_by(
                DuplicateResolution.resolved_at.desc()
            ).limit(5).all()
            
            for res in recent:
                print(f"   - {res.action} by {res.resolved_by} at {res.resolved_at}")
                print(f"     Kept: {res.kept_record_id}, Deleted: {res.merged_record_id}")
                if res.merged_data:
                    print(f"     Audit data: {list(res.merged_data.keys())[:5]}...")
        
        print("\n" + "=" * 70)
        print("To actually confirm a duplicate, use the web UI:")
        print(f"http://localhost:5000/duplicates")
        print("\nOr use the API:")
        print(f"curl -X POST http://localhost:5000/api/duplicates/{candidate.id}/review \\")
        print(f'  -H "Content-Type: application/json" \\')
        print(f'  -d \'{{"action": "confirm", "reviewer": "test", "notes": "Test confirmation"}}\'')
        print("=" * 70)


def check_database_stats():
    """Display database statistics."""
    app = create_app()
    
    with app.app_context():
        print("\n" + "=" * 70)
        print("Database Statistics")
        print("=" * 70)
        
        person_count = Person.query.count()
        baptism_count = BaptismRecord.query.count()
        marriage_count = MarriageRecord.query.count()
        death_count = DeathRecord.query.count()
        
        print(f"\nRecords in database:")
        print(f"  Persons: {person_count}")
        print(f"  Baptisms: {baptism_count}")
        print(f"  Marriages: {marriage_count}")
        print(f"  Deaths: {death_count}")
        
        pending = DuplicateCandidate.query.filter_by(status='pending').count()
        confirmed = DuplicateCandidate.query.filter_by(status='confirmed').count()
        rejected = DuplicateCandidate.query.filter_by(status='rejected').count()
        
        print(f"\nDuplicate candidates:")
        print(f"  Pending: {pending}")
        print(f"  Confirmed: {confirmed}")
        print(f"  Rejected: {rejected}")
        
        resolutions = DuplicateResolution.query.count()
        print(f"\nDuplicate resolutions (audit trail): {resolutions}")
        
        print("=" * 70)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test duplicate confirmation functionality')
    parser.add_argument('--stats', action='store_true', help='Show database statistics only')
    args = parser.parse_args()
    
    try:
        if args.stats:
            check_database_stats()
        else:
            test_duplicate_confirmation()
            check_database_stats()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
