"""
Script to fix marriage records by populating spouse1_id and spouse2_id fields.
This matches spouse names in marriage records to Person records.
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import MarriageRecord, Person
from sqlalchemy import and_, or_

def fix_marriage_spouses():
    """Fix all marriage records to populate spouse ID fields from Person records."""
    app = create_app()
    
    with app.app_context():
        # Get all marriage records
        marriages = MarriageRecord.query.all()
        updated_count = 0
        matched_spouse1 = 0
        matched_spouse2 = 0
        
        print(f"Found {len(marriages)} marriage records to check...")
        print()
        
        for marriage in marriages:
            updated = False
            
            # Try to match spouse1 if ID is missing but we have name data
            if not marriage.spouse1_id and (marriage.spouse1_name or marriage.spouse1_surname):
                # Build query to find matching person
                conditions = []
                
                if marriage.spouse1_name:
                    conditions.append(Person.first_name == marriage.spouse1_name)
                if marriage.spouse1_surname:
                    conditions.append(Person.last_name == marriage.spouse1_surname)
                
                if conditions:
                    # Try exact match first
                    spouse1 = Person.query.filter(and_(*conditions)).first()
                    
                    if spouse1:
                        marriage.spouse1_id = spouse1.id
                        updated = True
                        matched_spouse1 += 1
                        print(f"✓ Matched spouse1: {spouse1.first_name} {spouse1.last_name} (ID: {spouse1.id})")
                    else:
                        print(f"✗ No match for spouse1: {marriage.spouse1_name} {marriage.spouse1_surname}")
            
            # Try to match spouse2 if ID is missing but we have name data
            if not marriage.spouse2_id and (marriage.spouse2_name or marriage.spouse2_surname or marriage.spouse2_maiden_name):
                # Build query to find matching person
                conditions = []
                
                if marriage.spouse2_name:
                    conditions.append(Person.first_name == marriage.spouse2_name)
                
                # Try matching with surname or maiden name
                surname_conditions = []
                if marriage.spouse2_surname:
                    surname_conditions.append(Person.last_name == marriage.spouse2_surname)
                if marriage.spouse2_maiden_name:
                    surname_conditions.append(Person.maiden_name == marriage.spouse2_maiden_name)
                    surname_conditions.append(Person.last_name == marriage.spouse2_maiden_name)
                
                if surname_conditions:
                    conditions.append(or_(*surname_conditions))
                
                if conditions:
                    # Try exact match first
                    spouse2 = Person.query.filter(and_(*conditions)).first()
                    
                    if spouse2:
                        marriage.spouse2_id = spouse2.id
                        updated = True
                        matched_spouse2 += 1
                        print(f"✓ Matched spouse2: {spouse2.first_name} {spouse2.last_name} (ID: {spouse2.id})")
                    else:
                        print(f"✗ No match for spouse2: {marriage.spouse2_name} {marriage.spouse2_surname or marriage.spouse2_maiden_name}")
            
            if updated:
                updated_count += 1
                print(f"  Marriage date: {marriage.marriage_date}, Parish: {marriage.parish}")
                print()
        
        # Commit all changes
        if updated_count > 0:
            db.session.commit()
            print(f"\n{'='*60}")
            print(f"Successfully updated {updated_count} marriage records!")
            print(f"  - Matched {matched_spouse1} spouse1 records")
            print(f"  - Matched {matched_spouse2} spouse2 records")
            print(f"{'='*60}")
        else:
            print("\nNo marriage records needed updating.")

if __name__ == '__main__':
    fix_marriage_spouses()
