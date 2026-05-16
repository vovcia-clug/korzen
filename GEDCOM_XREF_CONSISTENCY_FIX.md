# GEDCOM XREF @ Symbol Consistency Fix

## Issue Summary

Found and fixed a critical inconsistency in how GEDCOM xref identifiers (e.g., `@I1@`, `@F4@`) were being handled with respect to the '@' symbol stripping.

## The Problem

In [`src/app/gedcom_parser.py`](src/app/gedcom_parser.py), there was an inconsistency in handling '@' symbols:

### ❌ Inconsistent Code (Lines 859-861)
```python
for sub in family.sub_records:
    if sub.tag == 'HUSB' and sub.value:
        husband_xref = sub.value.strip('@')  # STRIPS @ symbols
    elif sub.tag == 'WIFE' and sub.value:
        wife_xref = sub.value.strip('@')  # STRIPS @ symbols
```

This code was stripping '@' symbols when creating `GenealogicalRecord` raw_payload data.

### ✅ Consistent Code (Lines 526-528, 547-549, 662-664)
```python
# In create_marriage_record method:
if sub.tag == 'HUSB' and sub.value:
    xref = sub.value  # Keep @ symbols to match person_map keys

# In process_family_children method:
if sub.tag == 'HUSB' and sub.value:
    father_xref = sub.value  # Keep @ symbols
```

All other code correctly kept '@' symbols intact.

## Impact

The inconsistency caused:

1. **GenealogicalRecord.raw_payload** stored xrefs WITHOUT '@' symbols (e.g., "I1")
2. **person_map** keys had '@' symbols (e.g., "@I1@")
3. **Person.gedcom_id** stored WITH '@' symbols (e.g., "@I1@")
4. **All lookups** expected '@' symbols to be present

This mismatch required workaround code in [`fix_marriage_spouses_xref.py`](fix_marriage_spouses_xref.py:67):
```python
# Had to add @ symbols back because raw data didn't have them
husband_xref_with_at = f"@{husband_xref}@"
```

## The Fix

**File:** `src/app/gedcom_parser.py`  
**Lines:** 859-861

**Changed from:**
```python
if sub.tag == 'HUSB' and sub.value:
    husband_xref = sub.value.strip('@')
elif sub.tag == 'WIFE' and sub.value:
    wife_xref = sub.value.strip('@')
```

**Changed to:**
```python
if sub.tag == 'HUSB' and sub.value:
    husband_xref = sub.value  # Keep @ symbols for consistency
elif sub.tag == 'WIFE' and sub.value:
    wife_xref = sub.value  # Keep @ symbols for consistency
```

## Verification

The codebase now consistently handles GEDCOM xrefs:

### ✅ All locations keep '@' symbols:
- **Line 528:** `xref = sub.value` (HUSB in create_marriage_record)
- **Line 549:** `xref = sub.value` (WIFE in create_marriage_record)
- **Line 662:** `father_xref = sub.value` (HUSB in process_family_children)
- **Line 664:** `mother_xref = sub.value` (WIFE in process_family_children)
- **Line 678:** `child_xref = sub.value` (CHIL in process_family_children)
- **Line 859:** `husband_xref = sub.value` (HUSB in raw data - NOW FIXED)
- **Line 861:** `wife_xref = sub.value` (WIFE in raw data - NOW FIXED)

### ✅ All storage includes '@' symbols:
- `Person.gedcom_id` stores xrefs like "@I1@"
- `person_map` keys are xrefs like "@I1@"
- `GenealogicalRecord.raw_payload` now stores xrefs like "@I1@"

### ✅ All lookups expect '@' symbols:
- Line 337: `Person.query.filter_by(gedcom_id=individual.xref_id)`
- Line 531: `if xref in self.person_map:`
- Line 537: `Person.query.filter_by(gedcom_id=xref, ...)`
- Line 667: `self.person_map.get(father_xref)`
- Line 679: `self.person_map.get(child_xref)`

## Benefits

1. **Consistency:** All xref handling is now uniform across the codebase
2. **No workarounds needed:** Future code won't need to add/remove '@' symbols
3. **Clearer intent:** Comments explicitly state to keep '@' symbols
4. **Easier debugging:** xrefs always look the same in logs and database
5. **Future-proof:** New GEDCOM parsing code will follow the established pattern

## Related Files

- **Fixed:** `src/app/gedcom_parser.py` (lines 859, 861)
- **Workaround (no longer needed for new imports):** `fix_marriage_spouses_xref.py`
- **Documentation:** `MARRIAGE_SPOUSE_FIX_FINAL.md`

## Recommendation

For existing data that was imported with the old inconsistent code, the workaround script `fix_marriage_spouses_xref.py` can still be used. However, all new GEDCOM imports will now have consistent '@' symbol handling throughout.
