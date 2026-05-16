# Marriage Spouse Import Fix - Final Solution

## Problem Summary
Marriage records imported from GEDCOM files were missing spouse relationships. All marriages had `spouse1_id` and `spouse2_id` set to `NULL`, even though the spouse persons existed in the database.

## Root Cause
The issue was an **xref format mismatch** in the GEDCOM parser:

1. **Person records** are stored with GEDCOM IDs that include `@` symbols (e.g., `@I1@`)
   - Line 746 in `gedcom_parser.py`: `self.person_map[individual.xref_id] = str(person.id)`
   - The `individual.xref_id` includes `@` symbols

2. **Marriage creation** was stripping `@` symbols when looking up spouses
   - Lines 528 and 547: `xref = sub.value.strip('@')`
   - This caused lookups to fail because `person_map` keys had `@` symbols but the lookup was using stripped xrefs

3. **Raw genealogical records** also strip `@` symbols when storing family data
   - Lines 859 and 861: `husband_xref = sub.value.strip('@')`
   - This affected the fix script's ability to look up persons

## Solution Implemented

### 1. Fixed GEDCOM Parser ([`src/app/gedcom_parser.py`](src/app/gedcom_parser.py:525))

Changed the `create_marriage_record()` method to **NOT strip** `@` symbols when looking up spouses:

```python
# BEFORE (lines 528, 547):
xref = sub.value.strip('@')  # This caused the mismatch!

# AFTER:
xref = sub.value  # Keep @ symbols to match person_map keys
```

This ensures that:
- Spouse lookups use the correct xref format (with `@` symbols)
- `person_map` lookups succeed because keys match
- Future GEDCOM imports will correctly populate spouse relationships

### 2. Created Fix Script ([`fix_marriage_spouses_xref.py`](fix_marriage_spouses_xref.py))

Created a script to fix existing marriage records by:
1. Finding all marriages without spouse relationships
2. Looking up the raw genealogical records (FAMILY type)
3. Extracting husband/wife xrefs from raw payload (stored WITHOUT `@` symbols)
4. **Adding `@` symbols back** to match Person.gedcom_id format
5. Looking up Person records and updating marriage spouse fields

Key insight in the fix script:
```python
# Raw data has xrefs WITHOUT @ symbols (e.g., "I1")
# But Person.gedcom_id has them WITH @ symbols (e.g., "@I1@")
# So we need to add them back
husband_xref_with_at = f"@{husband_xref}@"
husband = Person.query.filter_by(gedcom_id=husband_xref_with_at).first()
```

## Results

### Before Fix
- Total marriages: 19
- Marriages with spouse1: 0 (0%)
- Marriages with spouse2: 0 (0%)

### After Fix
- Total marriages: 19
- Marriages with spouse1: 19 (100%)
- Marriages with spouse2: 19 (100%)

All 19 marriages now have both spouses correctly populated!

## How to Use

### For Existing Data
Run the fix script from the `src` directory:
```bash
cd /home/user/GitHub/korzen/src
python3 ../fix_marriage_spouses_xref.py
```

### For Future Imports
The parser fix ensures that all future GEDCOM imports will correctly populate spouse relationships automatically. No manual intervention needed.

## Files Modified

1. **[`src/app/gedcom_parser.py`](src/app/gedcom_parser.py:525-565)** - Fixed `create_marriage_record()` method
2. **[`fix_marriage_spouses_xref.py`](fix_marriage_spouses_xref.py)** - Script to fix existing data

## Technical Details

### GEDCOM xref Format
- GEDCOM files use xrefs like `@I1@`, `@I2@`, `@F1@` to reference individuals and families
- The `@` symbols are part of the GEDCOM standard format
- ged4py library preserves these symbols in `xref_id` attributes

### Database Storage
- `Person.gedcom_id`: Stored WITH `@` symbols (e.g., `@I1@`)
- `GenealogicalRecord.raw_payload`: Stored WITHOUT `@` symbols (e.g., `I1`)
- This inconsistency was the source of the bug

### The Fix
The fix ensures consistency by:
- Keeping `@` symbols throughout the marriage creation process
- Using the same format for lookups as stored in the database
- Adding `@` symbols back when reading from raw payload

## Verification

To verify marriages have spouses:
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

## Related Documentation
- [`MARRIAGE_SPOUSE_FIX.md`](MARRIAGE_SPOUSE_FIX.md) - Previous fix attempt (incomplete)
- [`GEDCOM_PARSER_IMPLEMENTATION.md`](GEDCOM_PARSER_IMPLEMENTATION.md) - Parser documentation
