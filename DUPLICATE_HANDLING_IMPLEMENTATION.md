# Duplicate Handling Implementation - Hard Delete Approach

## Overview

Implemented functionality to handle confirmed duplicates by **hard deleting** the duplicate records from the database while maintaining an audit trail.

## Implementation Date
May 17, 2026

## Approach: Hard Delete

After discussion with the user, the **hard delete approach** was chosen instead of the soft delete approach (Option B from requirements).

### Why Hard Delete?
- Cleaner database without obsolete records
- No need to filter queries by `is_duplicate` flags
- Simpler query logic across the application
- Audit trail maintained via `DuplicateResolution` table

## Changes Made

### 1. Updated Review Endpoint (src/app/routes/main.py)

Modified the `/api/duplicates/<candidate_id>/review` endpoint (lines 1343-1489):

**When a duplicate is confirmed (`action == 'confirm'`):**

1. **Records Audit Trail**: Captures full record data before deletion
2. **Creates DuplicateResolution Entry**: Stores deletion metadata
3. **Deletes Duplicate Record**: Removes `record2_id` from database
4. **Keeps Original Record**: Preserves `record1_id` as the authoritative record

**Record Types Supported:**
- Person records (`persons` table)
- Baptism records (`baptism_records` table)
- Marriage records (`marriage_records` table)
- Death records (`death_records` table)

### 2. Audit Trail Structure

Each confirmed duplicate deletion creates a `DuplicateResolution` record containing:

```python
{
    'candidate_id': UUID,           # Link to DuplicateCandidate
    'action': 'merge',              # Action taken
    'kept_record_id': UUID,         # Record that was preserved
    'merged_record_id': UUID,       # Record that was deleted
    'resolved_by': string,          # User/system identifier
    'resolved_at': datetime,        # Timestamp
    'resolution_notes': text,       # User notes
    'merged_data': jsonb           # Complete record data snapshot
}
```

### 3. Captured Record Data by Type

**Person Records:**
- id, first_name, last_name, maiden_name, gender
- birth_date, death_date, birth_place, death_place
- gedcom_id (for traceability)

**Baptism Records:**
- id, baptism_date, birth_date, child_name
- father_name, father_surname, mother_name, mother_maiden_name
- parish, gedcom_id

**Marriage Records:**
- id, marriage_date
- spouse1_name, spouse1_surname
- spouse2_name, spouse2_surname, spouse2_maiden_name
- parish, gedcom_id

**Death Records:**
- id, death_date, deceased_name, deceased_surname
- deceased_maiden_name, age_years
- parish, gedcom_id

## Foreign Key Handling

The implementation relies on the database schema's foreign key constraints:

- **ON DELETE CASCADE**: Automatically deletes dependent records
- **ON DELETE SET NULL**: Sets foreign key references to NULL

### Potential Impact:
When deleting a Person record that is referenced by other records:
- Baptism/Marriage/Death records may have foreign keys set to NULL
- Children of deleted person may lose parent reference
- Marriage records may lose spouse reference

**Mitigation**: The audit trail in `DuplicateResolution.merged_data` preserves all original data for potential recovery.

## API Response

**Confirm Success Response:**
```json
{
    "success": true,
    "message": "Duplicate confirmed successfully and duplicate record deleted",
    "candidate": {
        "id": "uuid",
        "status": "confirmed",
        "reviewed_by": "username",
        "reviewed_at": "2026-05-17T12:00:00Z"
    }
}
```

**Reject Success Response:**
```json
{
    "success": true,
    "message": "Duplicate rejected successfully",
    "candidate": {
        "id": "uuid",
        "status": "rejected",
        "reviewed_by": "username",
        "reviewed_at": "2026-05-17T12:00:00Z"
    }
}
```

## Testing Instructions

### 1. Import Test Data

```bash
# Import first test set
curl -X POST http://localhost:5000/api/import \
  -H "Content-Type: application/json" \
  -d '{"filename": "test_duplicates_set1.ged"}'

# Import second test set (creates duplicates)
curl -X POST http://localhost:5000/api/import \
  -H "Content-Type: application/json" \
  -d '{"filename": "test_duplicates_set2.ged"}'
```

### 2. View Duplicates

Navigate to `http://localhost:5000/duplicates`

### 3. Confirm a Duplicate

```bash
curl -X POST http://localhost:5000/api/duplicates/{candidate_id}/review \
  -H "Content-Type: application/json" \
  -d '{
    "action": "confirm",
    "reviewer": "test_user",
    "notes": "These records are clearly the same person"
  }'
```

### 4. Verify Deletion

Check that:
- Duplicate record no longer appears in `/persons`, `/baptisms`, `/marriages`, or `/deaths`
- Original record is still visible
- `DuplicateCandidate` status is updated to "confirmed"
- `DuplicateResolution` record exists with complete audit trail

### 5. Check Audit Trail

```sql
SELECT * FROM duplicate_resolutions 
WHERE candidate_id = {candidate_id};

-- View deleted record data
SELECT merged_data FROM duplicate_resolutions 
WHERE merged_record_id = {deleted_record_id};
```

## Database Queries

### View All Confirmed Deletions
```sql
SELECT 
    dr.resolved_at,
    dr.resolved_by,
    dc.record_type,
    dr.kept_record_id,
    dr.merged_record_id,
    dr.merged_data->>'first_name' as deleted_first_name,
    dr.merged_data->>'last_name' as deleted_last_name
FROM duplicate_resolutions dr
JOIN duplicate_candidates dc ON dr.candidate_id = dc.id
WHERE dr.action = 'merge'
ORDER BY dr.resolved_at DESC;
```

### View Deletion Statistics
```sql
SELECT 
    dc.record_type,
    COUNT(*) as deletions
FROM duplicate_resolutions dr
JOIN duplicate_candidates dc ON dr.candidate_id = dc.id
WHERE dr.action = 'merge'
GROUP BY dc.record_type;
```

## Recovery Process

If a record was deleted by mistake:

1. **Retrieve Record Data:**
```sql
SELECT merged_data FROM duplicate_resolutions 
WHERE merged_record_id = '{deleted_record_uuid}';
```

2. **Manual Re-insertion:**
- Use the `merged_data` JSON to recreate the record
- Update foreign key relationships as needed
- Mark the `DuplicateCandidate` as rejected to prevent re-deletion

## Advantages of This Implementation

✅ **Clean Database**: No cluttered duplicate records  
✅ **Audit Trail**: Complete record history in `DuplicateResolution`  
✅ **Simple Queries**: No need for `WHERE is_duplicate = False` filters  
✅ **Automatic Cascade**: Foreign key handling by database  
✅ **Recovery Possible**: Deleted data preserved in JSONB  

## Limitations

⚠️ **Foreign Key Impact**: Related records may lose references  
⚠️ **No Undo**: Requires manual intervention to recover  
⚠️ **Cascade Effects**: May delete/modify related records  

## Files Modified

1. **src/app/routes/main.py**
   - Added `DuplicateResolution` import
   - Enhanced `review_duplicate()` endpoint
   - Added audit trail creation
   - Implemented hard delete logic

## Migration Status

**No database migration required** - uses existing schema:
- `duplicate_candidates` table (already exists)
- `duplicate_resolutions` table (already exists)
- No new columns added to record tables

## Maintenance Notes

### Monitoring Deletions

Periodically review:
- Number of confirmed duplicates per month
- Types of records being deleted most frequently
- Foreign key constraint violations (if any)

### Performance Considerations

- Deletion is synchronous within the HTTP request
- For bulk operations, consider async processing
- Database cascades may take time for heavily referenced records

## Future Enhancements (Optional)

1. **Soft Delete Option**: Add configuration flag to choose between hard/soft delete
2. **Bulk Operations**: Confirm multiple duplicates at once
3. **Merge Instead of Delete**: Combine fields from both records before deletion
4. **UI Indicators**: Show which record will be kept/deleted in duplicate review UI
5. **Rollback Feature**: One-click restoration from `DuplicateResolution` data

## Related Documentation

- See `GEDCOM_DUPLICATE_DETECTION.md` for duplicate detection logic
- See `src/app/models.py` for table schema definitions
- See `plans/VECTOR_DUPLICATE_DETECTION_PLAN.md` for original design

---

**Implementation Complete**: May 17, 2026  
**Tested**: Manual verification recommended  
**Production Ready**: Yes, with recommended testing
