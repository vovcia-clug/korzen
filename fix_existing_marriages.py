"""
Script to fix existing marriage records by populating spouse IDs from GEDCOM data.
This reads the raw genealogical records and matches them to marriage records.
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import MarriageRecord, Person, GenealogicalRecord

def fix_existing_marriages():
    """Fix all marriage records by matching GEDCOM family records to persons."""
    app = create_app()
    
    with app.app_context():
        # Get all marriage records
        marriages = MarriageRecord.query.all()
        updated_count = 0
        
        print(f"Found {len(marriages)} marriage records to fix...")
        print()
        
        for marriage in marriages:
            if marriage.spouse1_id and marriage.spouse2_id:
                # Already has both spouses
                continue
            
            # Find the corresponding genealogical record
            if marriage.gedcom_id:
                # Extract family GEDCOM ID from marriage GEDCOM ID (format: FAM_ID_MARR)
                family_id = marriage.gedcom_id.replace('_MARR', '')
                
                # Find the genealogical record for this family
                gen_record = GenealogicalRecord.query.filter_by(
                    external_id=family_id,
                    record_type='FAMILY'
                ).first()
                
                if gen_record and gen_record.raw_payload:
                    updated = False
                    payload = gen_record.raw_payload
                    
                    # Get husband (spouse1)
                    if not marriage.spouse1_id and 'husband' in payload and payload['husband']:
                        husband_gedcom_id = payload['husband']
                        husband = Person.query.filter_by(
                            gedcom_id=husband_gedcom_id,
                            source_batch_id=marriage.source_batch_id
                        ).first()
                        
                        if husband:
                            marriage.spouse1_id = husband.id
                            marriage.spouse1_name = husband.first_name
                            marriage.spouse1_surname = husband.last_name
                            updated = True
                            print(f"✓ Matched spouse1 (husband): {husband.first_name} {husband.last_name}")
                        else:
                            print(f"✗ Could not find husband with GEDCOM ID: {husband_gedcom_id}")
                    
                    # Get wife (spouse2)
                    if not marriage.spouse2_id and 'wife' in payload and payload['wife']:
                        wife_gedcom_id = payload['wife']
                        wife = Person.query.filter_by(
                            gedcom_id=wife_gedcom_id,
                            source_batch_id=marriage.source_batch_id
                        ).first()
                        
                        if wife:
                            marriage.spouse2_id = wife.id
                            marriage.spouse2_name = wife.first_name
                            marriage.spouse2_surname = wife.last_name
                            marriage.spouse2_maiden_name = wife.maiden_name
                            updated = True
                            print(f"✓ Matched spouse2 (wife): {wife.first_name} {wife.last_name}")
                        else:
                            print(f"✗ Could not find wife with GEDCOM ID: {wife_gedcom_id}")
                    
                    if updated:
                        updated_count += 1
                        print(f"  Marriage date: {marriage.marriage_date}, Parish: {marriage.parish}")
                        print()
        
        # Commit all changes
        if updated_count > 0:
            db.session.commit()
            print(f"\n{'='*60}")
            print(f"Successfully updated {updated_count} marriage records!")
            print(f"{'='*60}")
        else:
            print("\nNo marriage records needed updating.")

if __name__ == '__main__':
    fix_existing_marriages()
