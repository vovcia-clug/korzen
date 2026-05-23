# NULL Value Handling Fix

## Issue
The OCR microservice was crashing when processing baptism records with the error:
```
'NoneType' object has no attribute 'strip'
```

This occurred in `church_records_parser.py` at line 128 when the parser tried to call `.strip()` on None values.

## Root Cause
The OpenRouter API can return `None` values for `given_names` and `surname` fields when OCR cannot reliably extract these values from historical church records. The parser was not handling these None values before calling string methods like `.strip()`.

## Changes Made

### 1. Fixed `_normalize_name` method (`church_records_parser.py`)
**Lines 316-334**

Added None checks before calling `.strip()`:
```python
# Before:
given_names = unidecode(record.given_names.strip())
surname = unidecode(record.surname.strip())

# After:
given_names = unidecode(record.given_names.strip()) if record.given_names else ""
surname = unidecode(record.surname.strip()) if record.surname else ""
```

Also added None checks before capitalizing:
```python
given_names = self._capitalize_name(given_names) if given_names else ""
surname = self._capitalize_name(surname) if surname else ""
```

### 2. Fixed `_parse_month` method (`church_records_parser.py`)
**Lines 393-406**

Added early return for None values:
```python
if not month_str:
    return None
    
month_lower = month_str.lower().strip()
```

### 3. Updated Data Models (`person_record.py`)
**Lines 7-35**

Changed `given_names` from required (`str`) to optional (`Optional[str] = None`) in all record types:
- `PersonRecord`
- `ParentRecord`
- `WitnessRecord`

This reflects the reality that OCR may fail to extract given names from historical documents.

## Impact
- The parser now gracefully handles missing name data
- Empty strings are used as defaults instead of crashing
- Records with partial data can still be processed
- Better resilience when processing low-quality or damaged historical documents

## Testing
To verify the fix works, process a church record with missing names:
```python
from ocr_microservice.src.models.person_record import PersonRecord

# Test with None values
person = PersonRecord(
    given_names=None,
    surname=None,
    full_name="Unknown"
)

# Should now work without errors
given, surname = parser._normalize_name(person)
assert given == ""
assert surname == ""
```
