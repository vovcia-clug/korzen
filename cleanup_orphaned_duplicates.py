#!/usr/bin/env python3
"""
Clean up orphaned DuplicateCandidate entries where referenced records no longer exist.
This fixes the "Record not found" issue on the Duplicates page.
"""

import os
import sys
from sqlalchemy import text

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.models import DuplicateCandidate, Person, BaptismRecord, MarriageRecord, DeathRecord
from app.extensions import db
from app import create_app

def cleanup_orphaned_candidates(dry_run=True):
    """
    Clean up DuplicateCandidate entries where one or both referenced records don't exist.
    
    Args:
        dry_run: If True, only report what would be deleted without actually deleting
    """
    
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("CLEANING UP ORPHANED DUPLICATE CANDIDATES")
        print("=" * 80)
        print(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will delete orphaned entries)'}")
        print()
        
        # Get all duplicate candidates
        all_candidates = DuplicateCandidate.query.all()
        print(f"Total duplicate candidates: {len(all_candidates)}")
        
        to_delete = []
        
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
            
            # Mark for deletion if either record is missing
            if not record1_exists or not record2_exists:
                to_delete.append(candidate)
        
        print(f"Orphaned candidates to delete: {len(to_delete)}")
        
        if to_delete:
            # Group by status for reporting
            by_status = {}
            for candidate in to_delete:
                status = candidate.status
                by_status[status] = by_status.get(status, 0) + 1
            
            print("\nBreakdown by status:")
            for status, count in by_status.items():
                print(f"  {status}: {count}")
            
            if not dry_run:
                print("\nDeleting orphaned candidates and their resolutions...")
                
                # First, delete any associated resolutions
                from app.models import DuplicateResolution
                candidate_ids = [c.id for c in to_delete]
                resolutions_deleted = DuplicateResolution.query.filter(
                    DuplicateResolution.candidate_id.in_(candidate_ids)
                ).delete(synchronize_session=False)
                
                print(f"  Deleted {resolutions_deleted} associated resolution records")
                
                # Now delete the candidates
                for candidate in to_delete:
                    db.session.delete(candidate)
                
                db.session.commit()
                print(f"✓ Successfully deleted {len(to_delete)} orphaned duplicate candidates")
            else:
                print("\n⚠ DRY RUN: No changes made. Run with dry_run=False to actually delete.")
        else:
            print("✓ No orphaned candidates found!")
        
        print("\n" + "=" * 80)
        print("CLEANUP COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up orphaned duplicate candidates')
    parser.add_argument('--execute', action='store_true', 
                       help='Actually delete orphaned entries (default is dry-run)')
    
    args = parser.parse_args()
    
    cleanup_orphaned_candidates(dry_run=not args.execute)
