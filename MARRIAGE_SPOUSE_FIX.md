# Marriage Spouse Fix

## Problem
When marriage records are loaded, the `spouse1` and `spouse2` relationship fields are empty (None), even though the marriage records exist in the database.

## Root Cause
The issue is in the GEDCOM parser's `create_marriage_record()` method. When processing family records to create marriages:

1. The method tries to look up spouse Person records using `self.person_map` 
2. If the GEDCOM xref is not found in `person_map`, it doesn't populate the spouse IDs or names
3. This results in marriage records with NULL spouse1_id and spouse2_id fields

## Solution Implemented

### 1. Fixed GEDCOM Parser (src/app/gedcom_parser.py)
Modified the `create_marriage_record()` method to add a fallback lookup:

```python
# Before: Only checked person_map
if xref in self.person_map:
    spouse1_id = self.person_map[xref]
    person = db.session.get(Person, spouse1_id)
    if person:
        spouse1_name = person.first_name
        spouse1_surname = person.last_name

# After: Check person_map first, then database
if xref in self.person_map:
    spouse1_id = self.person_map[xref]
    person = db.session.get(Person, spouse1_id)
else:
    # Fallback: try to find person by GEDCOM ID in database
    person = Person.query.filter_by(gedcom_id=xref, source_batch_id=self.batch.id).first()
    if person:
        spouse1_id = person.id
        # Update person_map for future lookups
        self.person_map[xref] = str(person.id)

if person:
    spouse1_name = person.first_name
    spouse1_surname = person.last_name
```

This ensures that:
- Spouse IDs are properly populated even if person_map is incomplete
- Spouse names are always set when a matching person is found
- The person_map cache is updated for future lookups

### 2. Fix Script for Existing Data
Created `fix_existing_marriages.py` to update existing marriage records by:
- Reading the raw genealogical records (FAMILY type)
- Extracting husband and wife GEDCOM IDs from the raw payload
- Looking up the corresponding Person records
- Updating the marriage records with the correct spouse IDs and names

## How to Fix Existing Data

### Option 1: Run the Fix Script
```bash
cd /home/user/GitHub/korzen
python3 fix_existing_marriages.py
```

### Option 2: Re-import the GEDCOM File
1. Reset the database (if needed)
2. Re-upload and parse the GEDCOM file
3. The fixed parser will now correctly populate spouse relationships

## Verification

After applying the fix, verify that marriages have spouses:

```python
from app import create_app
from app.extensions import db
from app.models import MarriageRecord
from sqlalchemy.orm import joinedload

app = create_app()
with app.app_context():
    marriages = MarriageRecord.query.options(
        joinedload(MarriageRecord.spouse1),
        joinedload(MarriageRecord.spouse2)
    ).limit(5).all()
    
    for marriage in marriages:
        print(f"Marriage on {marriage.marriage_date}:")
        if marriage.spouse1:
            print(f"  Spouse1: {marriage.spouse1.first_name} {marriage.spouse1.last_name}")
        if marriage.spouse2:
            print(f"  Spouse2: {marriage.spouse2.first_name} {marriage.spouse2.last_name}")
```

## Files Modified
- `src/app/gedcom_parser.py` - Fixed `create_marriage_record()` method (lines 516-565)
- `fix_existing_marriages.py` - New script to fix existing data
- `fix_marriage_spouses.py` - Alternative fix script (name-based matching)

## Template Already Correct
The marriage template (`src/app/templates/marriages.html`) already handles both cases:
- Shows `marriage.spouse1.first_name` if the relationship exists
- Falls back to `marriage.spouse1_name` if only text fields are populated

## Future Imports
All future GEDCOM imports will now correctly populate spouse relationships thanks to the parser fix.
