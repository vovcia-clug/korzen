# Duplicate Candidates "Record not found" Fix

## Problem Summary

The Duplicates page was showing many "Record not found" messages for both Record 1 and Record 2 in duplicate candidate pairs.

## Root Cause Analysis

**Diagnosis Results:**
- 180 out of 181 duplicate candidates referenced records that no longer existed in the database
- The `duplicate_candidates` table had no CASCADE delete constraints
- When records were deleted (manually or through duplicate confirmation), the `DuplicateCandidate` entries remained as orphans
- The database was likely reset on 2026-05-17, but the `duplicate_candidates` table wasn't cleared

## Solution Implemented

### 1. Database Migration (Permanent Fix)
Created migration: `add_cascade_to_duplicate_candidates.py`

**What it does:**
- Cleans up orphaned duplicate candidates on migration
- Creates PostgreSQL triggers to automatically delete duplicate candidates when referenced records are deleted
- Implements CASCADE-like behavior using database triggers (since we can't use FK constraints due to polymorphic references)

**Triggers created:**
- `cleanup_person_duplicates` - Deletes duplicate candidates when persons are deleted
- `cleanup_baptism_duplicates` - Deletes duplicate candidates when baptism records are deleted
- `cleanup_marriage_duplicates` - Deletes duplicate candidates when marriage records are deleted
- `cleanup_death_duplicates` - Deletes duplicate candidates when death records are deleted

### 2. Route Handler Update (Defensive Programming)
Updated [`duplicates()`](src/app/routes/main.py:1191) route to:
- Check if both records exist before displaying
- Skip orphaned candidates gracefully
- Log warnings for any orphaned entries found

### 3. Cleanup Scripts
Created diagnostic and cleanup utilities:
- [`diagnose_duplicate_records.py`](diagnose_duplicate_records.py) - Diagnoses orphaned candidates
- [`cleanup_orphaned_duplicates.py`](cleanup_orphaned_duplicates.py) - Cleans up orphaned candidates

## Results

**Before Fix:**
- Total duplicate candidates: 181
- Orphaned candidates: 180 (99.4%)
- Status breakdown:
  - Confirmed: 168
  - Pending: 10
  - Rejected: 2

**After Fix:**
- Total duplicate candidates: 1
- Orphaned candidates: 0 (0%)
- ✓ All duplicate candidates now reference existing records

## How It Prevents Future Issues

1. **Automatic Cleanup**: Database triggers automatically delete duplicate candidates when records are deleted
2. **Defensive Display**: The duplicates page now skips any orphaned entries that might slip through
3. **Logging**: Orphaned entries are logged for monitoring and debugging

## Testing

To verify the fix is working:

```bash
# Run diagnostic script
python diagnose_duplicate_records.py

# Expected output: "No orphaned candidates found!"
```

## Migration Applied

```bash
flask db upgrade
```

Migration revision: `add_cascade_duplicates`

## Files Modified

1. `src/migrations/versions/add_cascade_to_duplicate_candidates.py` - New migration
2. `src/app/routes/main.py` - Updated duplicates route handler
3. `diagnose_duplicate_records.py` - New diagnostic script
4. `cleanup_orphaned_duplicates.py` - New cleanup script
5. `DUPLICATE_CANDIDATES_FIX.md` - This documentation

## Future Considerations

If you need to manually clean up orphaned candidates in the future:

```bash
# Dry run (shows what would be deleted)
python cleanup_orphaned_duplicates.py

# Actually delete orphaned entries
python cleanup_orphaned_duplicates.py --execute
```

The database triggers should prevent this from happening again, but the scripts are available as a safety net.
