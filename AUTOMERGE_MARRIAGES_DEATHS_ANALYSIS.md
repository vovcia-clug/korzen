# Auto-Merge Status for Marriages and Deaths

## Summary

**Finding**: Automatic deletion after merging is **NOT implemented** for marriages and deaths during GEDCOM import. It is **ONLY implemented** for Person records.

However, **manual duplicate confirmation** (via the web interface) **DOES correctly delete** marriages and deaths from their respective tables.

## Detailed Analysis

### 1. Manual Duplicate Confirmation (Working ✅)

**File**: [`src/app/routes/main.py`](src/app/routes/main.py:1370-1478)

**Endpoint**: `POST /api/duplicates/<candidate_id>/review`

This endpoint correctly handles deletion for ALL record types when a duplicate is confirmed:

```python
if candidate.record_type == 'person':
    duplicate_record = db.session.get(Person, candidate.record2_id)
    kept_record = db.session.get(Person, candidate.record1_id)
elif candidate.record_type == 'baptism':
    duplicate_record = db.session.get(BaptismRecord, candidate.record2_id)
    kept_record = db.session.get(BaptismRecord, candidate.record1_id)
elif candidate.record_type == 'marriage':
    duplicate_record = db.session.get(MarriageRecord, candidate.record2_id)
    kept_record = db.session.get(MarriageRecord, candidate.record1_id)
elif candidate.record_type == 'death':
    duplicate_record = db.session.get(DeathRecord, candidate.record2_id)
    kept_record = db.session.get(DeathRecord, candidate.record1_id)

# ... later ...

# Delete from graph database first
graph_importer.delete_record_from_graph(candidate.record_type, record_uuid)

# Delete the duplicate record from PostgreSQL
db.session.delete(duplicate_record)
```

**Status**: ✅ **Working correctly** for marriages and deaths

### 2. Automatic Merge During GEDCOM Import (NOT Implemented ❌)

**File**: [`src/app/gedcom_parser.py`](src/app/gedcom_parser.py)

#### Current Implementation

The auto-merge feature during GEDCOM import has two phases:

1. **First Pass Auto-Merge** (lines 796-849):
   - Runs during person creation
   - Only handles Person records
   - Deletes duplicate persons immediately when 100% match found

2. **Post-Parse Auto-Merge** (lines 1050-1135):
   - Runs after all persons are imported
   - Only handles Person records
   - Finds and merges 100% duplicate persons

#### The `_auto_merge_duplicate` Method

**Location**: [`src/app/gedcom_parser.py:420`](src/app/gedcom_parser.py:420)

**Signature**: 
```python
def _auto_merge_duplicate(self, existing_person: Person, new_person: Person,
                         composite_score: float, score_breakdown: dict) -> None
```

**Key Observations**:
- Method signature specifically uses `Person` type hints
- Only called from person-related code paths
- No equivalent methods for marriages or deaths

#### Missing Implementation Areas

**Baptisms**: No auto-merge during import
- Baptism records are created in the second pass
- No duplicate checking or auto-merge logic exists
- All baptisms are imported, even if duplicates

**Marriages**: No auto-merge during import
- Marriage records are created in the third pass  
- No duplicate checking or auto-merge logic exists
- All marriages are imported, even if duplicates

**Deaths**: No auto-merge during import
- Death records are created in the second pass (as part of person processing)
- No duplicate checking or auto-merge logic exists
- All deaths are imported, even if duplicates

### 3. Documented Limitations

**File**: [`AUTO_MERGE_IMPLEMENTATION_SUMMARY.md`](AUTO_MERGE_IMPLEMENTATION_SUMMARY.md:219-226)

The documentation explicitly states:

> ## Known Limitations
> 
> 3. **Single Record Type**: Currently only implemented for Person records. Similar logic would need to be added for Baptism, Marriage, and Death records.
> 
> ## Future Enhancements
> 
> 2. **Extend to Other Records**: Implement auto-merge for baptisms, marriages, deaths

**Status**: ❌ **Not implemented** - documented as a known limitation

## Impact

### Current Behavior

When importing a GEDCOM file with duplicate marriages or deaths:

1. **During Import**:
   - All marriages are created, including 100% duplicates
   - All deaths are created, including 100% duplicates
   - Duplicate candidates may be created for manual review
   - No automatic merging occurs

2. **After Import** (Manual Review):
   - User can review duplicates in the web interface
   - When confirmed, duplicates ARE correctly deleted from tables
   - Graph database is synchronized (vertices and edges deleted)
   - Audit trail is created

### Data Consistency

- **PostgreSQL**: Duplicate marriages/deaths remain until manually confirmed
- **Graph Database**: Duplicate event vertices remain until manually confirmed  
- **Manual Cleanup**: Required for marriages and deaths (unlike persons which auto-merge)

## Recommendation

To achieve consistent behavior across all record types, the auto-merge feature should be extended to handle:

1. **Baptism Records**: During second pass
2. **Marriage Records**: During third pass
3. **Death Records**: During second pass

This would require:
- Creating `_auto_merge_baptism_duplicate()` method
- Creating `_auto_merge_marriage_duplicate()` method
- Creating `_auto_merge_death_duplicate()` method
- Adding duplicate detection in respective creation passes
- Handling GEDCOM ID mappings for events (if needed)

## Conclusion

**Answer to Original Question**: 

- ✅ **Manual duplicate confirmation**: YES, it correctly deletes from marriages and deaths tables
- ❌ **Automatic merge during import**: NO, it does NOT work for marriages and deaths (only for persons)

The auto-merge feature needs to be extended to support baptisms, marriages, and deaths to provide consistent duplicate handling across all record types.
