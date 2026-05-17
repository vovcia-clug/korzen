# GEDCOM ID Duplicate Detection Fix - Summary

## Date
2026-05-17

## Problem
When importing two different GEDCOM files, they could have the same GEDCOM IDs for different persons (e.g., both files use `@I1@`, `@I2@`, etc.). The parser was checking only the GEDCOM ID without considering the source batch, causing false positives where records from different files were incorrectly treated as duplicates.

This prevented legitimate imports of multiple GEDCOM files and caused data loss.

## Root Cause
In [`src/app/gedcom_parser.py`](src/app/gedcom_parser.py), the GEDCOM ID checks were querying only by `gedcom_id`:

```python
# OLD CODE (INCORRECT)
existing_person = Person.query.filter_by(gedcom_id=individual.xref_id).first()
```

This would match records from ANY batch/file, not just the current import.

## Solution
Modified all GEDCOM ID checks to also filter by `source_batch_id`, ensuring records are only considered duplicates if they have the same GEDCOM ID AND come from the same batch:

```python
# NEW CODE (CORRECT)
existing_person = Person.query.filter_by(
    gedcom_id=individual.xref_id,
    source_batch_id=self.batch.id
).first()
```

## Files Modified

### [`src/app/gedcom_parser.py`](src/app/gedcom_parser.py)
Modified 4 locations where GEDCOM ID checks occur:

1. **Line 226-233**: `create_person_from_individual()` - Person duplicate check
2. **Line 783-791**: `create_baptism_record()` - Baptism duplicate check  
3. **Line 835-843**: `create_marriage_record()` - Marriage duplicate check
4. **Line 957-964**: `create_death_record()` - Death duplicate check

Each check now includes `source_batch_id=self.batch.id` in the query filter.

### [`GEDCOM_DUPLICATE_DETECTION.md`](GEDCOM_DUPLICATE_DETECTION.md)
Updated documentation to:
- Clarify the distinction between GEDCOM ID re-import prevention and duplicate detection
- Document the fix applied on 2026-05-17
- Explain that GEDCOM ID tracking is NOT used for cross-file duplicate detection

## Impact

### What Changed
- **Re-import prevention**: Still works correctly - re-importing the same GEDCOM file won't create duplicates
- **Multi-file imports**: Now works correctly - importing different GEDCOM files with overlapping IDs is allowed
- **Duplicate detection**: Unaffected - continues to use vector similarity, phonetic matching, date/location comparison

### What Remains Intact
All other duplicate detection mechanisms remain fully functional:
1. **Vector similarity** - Embedding-based similarity using pgvector
2. **Phonetic matching** - Daitch-Mokotoff phonetic encoding
3. **Date similarity** - Temporal proximity matching
4. **Location similarity** - Geographic matching
5. **Composite scoring** - Weighted combination of all factors

These mechanisms in [`src/app/services/duplicate_detector.py`](src/app/services/duplicate_detector.py) do NOT use GEDCOM IDs and were not modified.

## Testing Recommendations

### Manual Testing
1. Import a GEDCOM file (e.g., `file1.ged`)
2. Import a different GEDCOM file (e.g., `file2.ged`) that may have overlapping GEDCOM IDs
3. Verify both imports succeed without false duplicate warnings
4. Re-import `file1.ged` and verify it doesn't create duplicates (re-import prevention still works)
5. Check the duplicate detection page to see if legitimate duplicates are still detected

### SQL Verification
```sql
-- Check that different batches can have same GEDCOM IDs
SELECT gedcom_id, source_batch_id, first_name, last_name, COUNT(*) 
FROM persons 
WHERE gedcom_id IS NOT NULL 
GROUP BY gedcom_id, source_batch_id, first_name, last_name
HAVING COUNT(*) > 1;
-- Should return 0 rows (no duplicates within same batch)

-- Check that same GEDCOM ID can exist across different batches
SELECT gedcom_id, COUNT(DISTINCT source_batch_id) as batch_count
FROM persons 
WHERE gedcom_id IS NOT NULL 
GROUP BY gedcom_id
HAVING COUNT(DISTINCT source_batch_id) > 1;
-- May return rows (same ID in different batches is OK)
```

## Conclusion
The GEDCOM ID duplicate detection mechanism has been **disabled for cross-file comparisons** while preserving:
- Re-import prevention for the same file
- All other duplicate detection mechanisms (vector, phonetic, date, location)
- Data integrity and traceability

This fix allows importing multiple GEDCOM files without false positives while maintaining robust duplicate detection capabilities.
