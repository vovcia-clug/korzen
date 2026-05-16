#!/usr/bin/env python3
"""
Fix existing marriage records by populating spouse relationships.

This script fixes marriages that were imported with the xref mismatch bug,
where spouse IDs were not populated because the lookup was using stripped
xrefs while person_map had xrefs with @ symbols.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import MarriageRecord, Person, GenealogicalRecord


def fix_marriages():
    """Fix marriage records by populating spouse relationships from raw data."""
    app = create_app()
    
    with app.app_context():
        # Get all marriages without spouse relationships
        marriages_to_fix = MarriageRecord.query.filter(
            (MarriageRecord.spouse1_id.is_(None)) | (MarriageRecord.spouse2_id.is_(None))
        ).all()
        
        print(f"Found {len(marriages_to_fix)} marriages to fix")
        
        fixed_count = 0
        error_count = 0
        
        for marriage in marriages_to_fix:
            try:
                # Extract family xref from gedcom_id (e.g., '@F4@_MARR' -> '@F4@')
                if not marriage.gedcom_id:
                    print(f"  Skipping marriage {marriage.id} - no gedcom_id")
                    continue
                
                family_xref = marriage.gedcom_id.replace('_MARR', '')
                
                # Find the raw genealogical record
                gen_record = GenealogicalRecord.query.filter_by(
                    external_id=family_xref,
                    record_type='FAMILY'
                ).first()
                
                if not gen_record:
                    print(f"  No raw record found for marriage {marriage.id} (family {family_xref})")
                    error_count += 1
                    continue
                
                # Extract husband and wife xrefs from raw payload
                husband_xref = gen_record.raw_payload.get('husband')
                wife_xref = gen_record.raw_payload.get('wife')
                
                updated = False
                
                # Look up husband
                if husband_xref and not marriage.spouse1_id:
                    # Raw data has xrefs WITHOUT @ symbols (e.g., "I1")
                    # But Person.gedcom_id has them WITH @ symbols (e.g., "@I1@")
                    # So we need to add them back
                    husband_xref_with_at = f"@{husband_xref}@"
                    husband = Person.query.filter_by(gedcom_id=husband_xref_with_at).first()
                    
                    if husband:
                        marriage.spouse1_id = husband.id
                        marriage.spouse1_name = husband.first_name
                        marriage.spouse1_surname = husband.last_name
                        updated = True
                        print(f"  Fixed spouse1 for marriage {marriage.id}: {husband.first_name} {husband.last_name}")
                    else:
                        print(f"  Could not find husband @{husband_xref}@ for marriage {marriage.id}")
                
                # Look up wife
                if wife_xref and not marriage.spouse2_id:
                    # Raw data has xrefs WITHOUT @ symbols (e.g., "I2")
                    # But Person.gedcom_id has them WITH @ symbols (e.g., "@I2@")
                    # So we need to add them back
                    wife_xref_with_at = f"@{wife_xref}@"
                    wife = Person.query.filter_by(gedcom_id=wife_xref_with_at).first()
                    
                    if wife:
                        marriage.spouse2_id = wife.id
                        marriage.spouse2_name = wife.first_name
                        marriage.spouse2_surname = wife.last_name
                        marriage.spouse2_maiden_name = wife.maiden_name
                        updated = True
                        print(f"  Fixed spouse2 for marriage {marriage.id}: {wife.first_name} {wife.last_name}")
                    else:
                        print(f"  Could not find wife @{wife_xref}@ for marriage {marriage.id}")
                
                if updated:
                    fixed_count += 1
                    
            except Exception as e:
                print(f"  Error fixing marriage {marriage.id}: {e}")
                error_count += 1
                import traceback
                traceback.print_exc()
        
        # Commit all changes
        if fixed_count > 0:
            db.session.commit()
            print(f"\n✓ Successfully fixed {fixed_count} marriages")
        else:
            print("\nNo marriages were fixed")
        
        if error_count > 0:
            print(f"✗ {error_count} errors occurred")
        
        # Verify the fix
        print("\n" + "="*60)
        print("VERIFICATION")
        print("="*60)
        
        total_marriages = MarriageRecord.query.count()
        marriages_with_spouse1 = MarriageRecord.query.filter(MarriageRecord.spouse1_id.isnot(None)).count()
        marriages_with_spouse2 = MarriageRecord.query.filter(MarriageRecord.spouse2_id.isnot(None)).count()
        
        print(f"Total marriages: {total_marriages}")
        print(f"Marriages with spouse1: {marriages_with_spouse1} ({marriages_with_spouse1*100//total_marriages if total_marriages else 0}%)")
        print(f"Marriages with spouse2: {marriages_with_spouse2} ({marriages_with_spouse2*100//total_marriages if total_marriages else 0}%)")


if __name__ == '__main__':
    fix_marriages()
