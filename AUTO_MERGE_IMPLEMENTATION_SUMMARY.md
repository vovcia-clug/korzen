# Automatic Duplicate Merging Implementation Summary

## Overview
This document summarizes the implementation of automatic merging for duplicate records with 100% similarity match during GEDCOM parsing.

## Changes Made

### 1. Configuration Constants (`src/app/gedcom_constants.py`)

Added two new configuration options:

```python
# Auto-merge configuration
AUTO_MERGE_THRESHOLD = 1.0  # Only auto-merge at 100% similarity  
ENABLE_AUTO_MERGE = True    # Feature flag to enable/disable auto-merge
```

**Purpose**: 
- `AUTO_MERGE_THRESHOLD`: Defines the threshold score (1.0 = 100%) required for automatic merging
- `ENABLE_AUTO_MERGE`: Feature flag to toggle the auto-merge functionality on/off

### 2. Enhanced GEDCOM Parser (`src/app/gedcom_parser.py`)

#### A. Updated Imports
Added imports for `DuplicateCandidate` and `DuplicateResolution` models to create audit trail entries.

```python
from .models import (
    ...
    DuplicateCandidate,
    DuplicateResolution
)
from .gedcom_constants import (
    ...
    AUTO_MERGE_THRESHOLD,
    ENABLE_AUTO_MERGE
)
```

#### B. Modified `_check_for_duplicates()` Method
Changed return type from `None` to `list` to return duplicate candidates for evaluation:

```python
def _check_for_duplicates(self, person: Person) -> list:
    """
    Check for potential duplicates and log warnings.
    
    Returns:
        List of tuples (candidate_person, composite_score, score_breakdown)
    """
    ...
    return duplicates
```

#### C. Created `_auto_merge_duplicate()` Helper Method
New method to handle automatic merging with full audit trail:

```python
def _auto_merge_duplicate(self, existing_person: Person, new_person: Person, 
                         composite_score: float, score_breakdown: dict) -> None:
    """
    Automatically merge a 100% duplicate by creating audit trail.
    
    - Deletes pending duplicate candidates created by detector
    - Creates confirmed DuplicateCandidate with status='confirmed'
    - Creates DuplicateResolution audit entry with action='merge'
    - Stores merged data in JSON for transparency
    - Logs the auto-merge action
    """
```

**Features**:
- Removes any "pending" duplicate candidates automatically created by the detector
- Creates a "confirmed" duplicate candidate record
- Creates a resolution audit entry with full details
- Stores the would-be duplicate's data in JSON format
- Logs the merge with full person details

#### D. Enhanced Person Creation Flow (`_first_pass_create_persons()`)

Modified the first pass to check for 100% matches after person creation:

```python
for individual in reader.records0('INDI'):
    person = self.create_person_from_individual(individual)
    db.session.add(person)
    db.session.flush()
    
    # Check for potential duplicates
    duplicates = self._check_for_duplicates(person)
    
    # Handle 100% matches with auto-merge
    should_keep_person = True
    if ENABLE_AUTO_MERGE and duplicates:
        for candidate, score, breakdown in duplicates:
            if score >= AUTO_MERGE_THRESHOLD:
                # Auto-merge logic
                self._auto_merge_duplicate(candidate, person, score, breakdown)
                db.session.delete(person)
                db.session.flush()
                self.person_map[individual.xref_id] = str(candidate.id)
                should_keep_person = False
                break
    
    if should_keep_person:
        self.person_map[individual.xref_id] = str(person.id)
        stats['persons'] += 1
```

**Workflow**:
1. Create person record and add to database
2. Flush to database (required for vector similarity search)
3. Detect duplicates using vector/phonetic/date/location matching
4. If any duplicate has ≥100% similarity:
   - Create audit trail entries
   - Delete the newly created person (it's a duplicate)
   - Map GEDCOM ID to existing person's ID
   - Skip incrementing person counter
5.  Otherwise, keep the new person and increment counter

## Audit Trail

### DuplicateCandidate Table
Auto-merged records create entries with:
- `status`: `'confirmed'` (NOT `'pending'`)
- `reviewed_by`: `'system_auto_merge'`
- `reviewed_at`: Current timestamp
- `review_notes`: `"Automatically merged - 100% match during GEDCOM import"`
- `composite_score`: 1.0 (100%)
- Individual similarity scores (vector, phonetic, date, location)

### DuplicateResolution Table
Auto-merged records create resolution entries with:
- `action`: `'merge'`
- `resolved_by`: `'system_auto_merge'`
- `resolved_at`: Current timestamp
- `resolution_notes`: Detailed description including GEDCOM IDs and person details
- `merged_data`: JSON snapshot of the would-be duplicate's data
- `kept_record_id`: ID of the existing person that was kept
- `merged_record_id`: ID of the existing person (since duplicate was deleted)

## Logging

Enhanced logging throughout the process:
- Warning logs for each duplicate detected (with similarity scores)
- Info logs when 100% match is detected
- Info logs for successful auto-merge operations
- Error logs if auto-merge fails

Example log output:
```
WARNING - Found 1 potential duplicate(s) for Jan Kowalski (GEDCOM ID: @I001@)
WARNING -   - Match: Jan Kowalski (ID: abc-123, Score: 1.00, Vector: 1.00, Phonetic: 1.00)
INFO - Detected 100% match for Jan Kowalski, auto-merging...
INFO - Auto-merged 100% duplicate: Jan Kowalski (GEDCOM: @I001@) -> Existing ID: abc-123. Score: 1.00
INFO - Auto-merge complete. GEDCOM ID @I001@ mapped to existing person abc-123
```

## Benefits

1. **Automatic De-duplication**: 100% matches are automatically merged without manual intervention
2. **Full Audit Trail**: Complete record of what was merged and when
3. **Transparency**: Merged data is preserved in JSON for review
4. **Configurable**: Can be enabled/disabled via feature flag
5. **Threshold Control**: Auto-merge threshold can be adjusted
6. **Manual Review Preserved**: <100% matches still go to duplicate_candidates for manual review
7. **Performance**: Reduces database size by preventing duplicate creation
8. **Data Integrity**: Original GEDCOM IDs are properly mapped to existing records

## Configuration Options

### To Disable Auto-Merge
In `src/app/gedcom_constants.py`:
```python
ENABLE_AUTO_MERGE = False
```

### To Adjust Threshold
To auto-merge matches with ≥95% similarity:
```python
AUTO_MERGE_THRESHOLD = 0.95
```

**Note**: Setting threshold below 1.0 is not recommended without careful testing, as it may merge records that are similar but not identical.

## Testing

A comprehensive test script (`test_auto_merge.py`) has been created to verify the functionality:

### Test Scenario
1. Import `test_duplicates_set1.ged` (baseline data with 5 persons)
2. Import `test_duplicates_set2.ged` (contains exact and near duplicates)
3. Verify 100% matches are auto-merged
4. Verify <100% matches go to manual review

### Expected Results
- Exact duplicates (100% similarity) should NOT be created as new records
- They should appear in `duplicate_resolutions` table with status='auto-merged'
- Near duplicates (<100% similarity) should appear in `duplicate_candidates` for manual review

## Implementation Status

✅ Configuration constants added  
✅ Helper method `_auto_merge_duplicate()` created  
✅ Duplicate detection modified to return candidates  
✅ Person creation flow updated to check for 100% matches  
✅ Audit trail implementation complete  
✅ Logging enhanced throughout  
✅ Test script created  

## Known Limitations

1. **Post-Detection Processing**: The `DuplicateDetector` service automatically saves all candidates to the database before our auto-merge logic runs. While we delete these "pending" entries, there's a brief moment where they exist.

2. **Vector Search Requirement**: Person must be flushed to database before duplicate detection (required for vector similarity search using pgvector).

3. **Single Record Type**: Currently only implemented for Person records. Similar logic would need to be added for Baptism, Marriage, and Death records.

##  Future Enhancements

1. **Batch Processing**: Delete pending candidates in batch for better performance
2. **Extend to Other Records**: Implement auto-merge for baptisms, marriages, deaths
3. **Configurable by Record Type**: Different thresholds for different record types
4. **Statistics Tracking**: Add counters to statistics dictionary for auto-merged records
5. **Rollback Capability**: Add functionality to "unmerge" auto-merged records if needed

## Conclusion

The automatic duplicate merging feature has been successfully implemented for Person records during GEDCOM import. The system now:
- Automatically merges records with 100% similarity
- Maintains full audit trail of all merges
- Preserves manual review workflow for near-duplicates
- Provides configurable thresholds and feature toggle
- Logs all operations for transparency

Records with similarity scores below 100% continue to be flagged for manual review in the `duplicate_candidates` table, ensuring that potentially different records aren't incorrectly merged.
