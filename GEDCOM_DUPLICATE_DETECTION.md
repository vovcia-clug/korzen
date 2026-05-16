# GEDCOM Duplicate Detection Implementation

## Overview

This document describes the implementation of GEDCOM ID tracking across all record types (Person, BaptismRecord, MarriageRecord, DeathRecord) to prevent duplicate records during re-import of GEDCOM files.

## Problem Statement

Previously, no record types stored original GEDCOM IDs, which caused:
- **Duplicate records**: Re-importing the same GEDCOM file created duplicate entries for persons, baptisms, marriages, and deaths
- **No traceability**: Unable to link records back to their original GEDCOM source
- **Data integrity issues**: Multiple imports resulted in data inconsistency across all record types

## Solution

### 1. Database Schema Changes

Added two new fields to **all record tables** (`persons`, `baptism_records`, `marriage_records`, `death_records`):

```python
# Source tracking for GEDCOM imports
gedcom_id = db.Column(String(50), nullable=True, index=True)
source_batch_id = db.Column(
    UUID(as_uuid=True),
    ForeignKey("record_batches.id"),
    nullable=True,
)
```

**Fields:**
- `gedcom_id`: Stores the original GEDCOM identifier (e.g., "@I123@")
- `source_batch_id`: Links to the RecordBatch that first imported this person
- Index on `gedcom_id`: Enables fast duplicate lookups during import

**Relationship:**
```python
source_batch = relationship("RecordBatch")
```

### 2. Parser Logic Updates

Modified `GedcomParser.create_person_from_individual()` to:

1. **Check for existing persons** before creating new ones:
```python
existing_person = Person.query.filter_by(gedcom_id=individual.xref_id).first()

if existing_person:
    logger.info(f"Found existing person with GEDCOM ID {individual.xref_id}")
    return existing_person
```

2. **Store GEDCOM ID and batch** when creating new persons:
```python
person = Person(
    gedcom_id=individual.xref_id,
    source_batch_id=self.batch.id,
    # ... other fields
)
```

### 3. Database Migrations

Created two migration files:

**Migration 1:** `src/migrations/versions/add_gedcom_id_tracking_to_persons.py`
- Adds GEDCOM ID tracking to `persons` table

**Migration 2:** `src/migrations/versions/add_gedcom_id_tracking_to_records.py`
- Adds GEDCOM ID tracking to `baptism_records`, `marriage_records`, and `death_records` tables

**Upgrade operations:**
- Add `gedcom_id` column (String, 50 chars, nullable, indexed)
- Add `source_batch_id` column (UUID, nullable)
- Create index on `gedcom_id` for fast lookups
- Create foreign key constraint to `record_batches` table

**Downgrade operations:**
- Drop foreign key constraint
- Drop index
- Drop both columns

## Usage

### Running the Migration

To apply the database changes:

```bash
# Using Docker
docker-compose exec web flask db upgrade

# Or locally
cd src
flask db upgrade
```

### Testing Duplicate Detection

1. **First import** of a GEDCOM file:
   - Creates new Person records
   - Stores GEDCOM IDs in `gedcom_id` field
   - Links to import batch via `source_batch_id`

2. **Second import** of the same GEDCOM file:
   - Finds existing persons by `gedcom_id`
   - Reuses existing Person records
   - No duplicate persons created
   - Log message: "Found existing person with GEDCOM ID..."

### Verification

Run the test script to verify implementation:

```bash
python test_gedcom_duplicate_detection.py
```

Expected output:
```
✓ Person.gedcom_id field exists
✓ Person.source_batch_id field exists
✓ Person.source_batch relationship exists
✓ Duplicate detection logic found
✓ GEDCOM ID is stored when creating persons
✓ Source batch ID is stored when creating persons
✓ Migration file found
```

## Benefits

1. **Duplicate Prevention**: Re-importing the same GEDCOM file won't create duplicate persons
2. **Data Lineage**: Track which batch/file each person came from
3. **Update Capability**: Foundation for updating existing persons with new information
4. **Merge Support**: Enables future person merging from different sources
5. **Audit Trail**: Complete history of data origin
6. **Performance**: Indexed lookups ensure fast duplicate detection

## Implementation Details

### Files Modified

1. **`src/app/models.py`**
   - Added `gedcom_id` field to Person model (line 87-88)
   - Added `source_batch_id` field to Person model (line 89-93)
   - Added `source_batch` relationship (line 125)

2. **`src/app/gedcom_parser.py`**
   - Added duplicate detection in `create_person_from_individual()` (line 340-345)
   - Store GEDCOM ID when creating persons (line 407)
   - Store source batch ID when creating persons (line 408)

3. **`src/migrations/versions/add_gedcom_id_tracking_to_persons.py`**
   - New migration file for database schema changes

### Backward Compatibility

- Both new fields are **nullable** to support:
  - Existing persons in the database (no GEDCOM ID)
  - Manually-entered persons (not from GEDCOM import)
  - Future import from other sources

### Edge Cases Handled

1. **Existing data**: Current persons without `gedcom_id` continue to work
2. **Manual entries**: Persons created manually have `gedcom_id=None`
3. **Multiple sources**: Different GEDCOM files can have same IDs (tracked by batch)
4. **Partial imports**: Failed imports don't leave orphaned data

## Future Enhancements

Potential improvements for future development:

1. **Conflict Resolution**: Define strategy when re-imported data differs from existing
2. **Update Mode**: Option to update existing person data on re-import
3. **Merge Tool**: UI for merging duplicate persons from different sources
4. **Composite Keys**: Add unique constraint on (gedcom_id, source_file)
5. **Import History**: Track all batches that referenced each person

## Testing

### Manual Testing Steps

1. Import a GEDCOM file and note the person count
2. Import the same file again
3. Verify person count remains the same (no duplicates)
4. Check logs for "Found existing person with GEDCOM ID" messages
5. Query database to verify `gedcom_id` values are populated

### SQL Verification

```sql
-- Check persons with GEDCOM IDs
SELECT id, gedcom_id, first_name, last_name, source_batch_id 
FROM persons 
WHERE gedcom_id IS NOT NULL;

-- Count persons by batch
SELECT source_batch_id, COUNT(*) 
FROM persons 
WHERE source_batch_id IS NOT NULL 
GROUP BY source_batch_id;

-- Find persons without GEDCOM IDs (manual entries)
SELECT id, first_name, last_name 
FROM persons 
WHERE gedcom_id IS NULL;
```

## Troubleshooting

### Issue: Duplicates still created

**Possible causes:**
- Migration not run: Check if `gedcom_id` column exists
- Parser not updated: Verify duplicate detection code is present
- Database transaction issues: Check logs for rollback messages

**Solution:**
```bash
# Verify migration status
docker-compose exec web flask db current

# Check column exists
docker-compose exec db psql -U korzen_user -d korzen_db -c "\d persons"
```

### Issue: Migration fails

**Possible causes:**
- Database connection issues
- Existing data conflicts
- Permission problems

**Solution:**
```bash
# Check database connection
docker-compose exec web flask db current

# View migration history
docker-compose exec web flask db history

# Rollback if needed
docker-compose exec web flask db downgrade
```

## References

- Person Model: [`src/app/models.py`](src/app/models.py)
- GEDCOM Parser: [`src/app/gedcom_parser.py`](src/app/gedcom_parser.py)
- Migration: [`src/migrations/versions/add_gedcom_id_tracking_to_persons.py`](src/migrations/versions/add_gedcom_id_tracking_to_persons.py)
- Test Script: [`test_gedcom_duplicate_detection.py`](test_gedcom_duplicate_detection.py)
