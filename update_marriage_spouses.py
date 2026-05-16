"""
Script to update existing marriage records with spouse names from Person records.
This fixes the issue where marriages were created without spouse name fields populated.
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import MarriageRecord, Person

def update_marriage_spouses():
    """Update all marriage records to populate spouse name fields from Person records."""
    app = create_app()
    
    with app.app_context():
        # Get all marriage records
        marriages = MarriageRecord.query.all()
        updated_count = 0
        
        print(f"Found {len(marriages)} marriage records to check...")
        
        for marriage in marriages:
            updated = False
            
            # Update spouse1 information if ID exists but names are missing
            if marriage.spouse1_id and not marriage.spouse1_name:
                spouse1 = db.session.get(Person, marriage.spouse1_id)
                if spouse1:
                    marriage.spouse1_name = spouse1.first_name
                    marriage.spouse1_surname = spouse1.last_name
                    updated = True
                    print(f"  Updated spouse1: {spouse1.first_name} {spouse1.last_name}")
            
            # Update spouse2 information if ID exists but names are missing
            if marriage.spouse2_id and not marriage.spouse2_name:
                spouse2 = db.session.get(Person, marriage.spouse2_id)
                if spouse2:
                    marriage.spouse2_name = spouse2.first_name
                    marriage.spouse2_surname = spouse2.last_name
                    marriage.spouse2_maiden_name = spouse2.maiden_name
                    updated = True
                    print(f"  Updated spouse2: {spouse2.first_name} {spouse2.last_name}")
            
            if updated:
                updated_count += 1
        
        # Commit all changes
        db.session.commit()
        print(f"\nSuccessfully updated {updated_count} marriage records!")

if __name__ == '__main__':
    update_marriage_spouses()
