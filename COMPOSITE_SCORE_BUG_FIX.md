# Composite Score Bug Fix Summary

## Bug Description

The [`save_duplicate_candidate()`](src/app/services/duplicate_detector.py:1003) method had a critical bug where it incorrectly recalculated the composite score using a fixed-weight formula that treated `None` values (from missing data masking) as `0.0`.

### Symptoms
1. Component scores stored as `0.0` when they should be `None`
2. Composite score calculated incorrectly without normalization
3. Mathematical impossibility: Composite = 1.0 with all components = 0.0

### Root Cause

Lines 1059-1065 in the original code:
```python
# INCORRECT - treats None as 0.0
composite_score = (
    self.WEIGHT_VECTOR * scores['vector_sim'] +
    self.WEIGHT_PHONETIC * scores['phonetic_sim'] +  # None becomes 0.0
    self.WEIGHT_DATE * scores['date_sim'] +          # None becomes 0.0
    self.WEIGHT_LOCATION * scores['location_sim']    # None becomes 0.0
)
```

When [`calculate_composite_score()`](src/app/services/duplicate_detector.py:453) returns `None` for missing data components, the multiplication treats them as `0.0`, resulting in an incorrect composite score.

## Solution Implemented

**Option 1 (Preferred):** Pass the already-calculated composite score to [`save_duplicate_candidate()`](src/app/services/duplicate_detector.py:1003)

### Changes Made

#### 1. Updated Method Signature (Line 1003)

**Before:**
```python
def save_duplicate_candidate(
    self,
    record_type: str,
    record1_id: UUID,
    record2_id: UUID,
    scores: dict,
    method: str = 'auto'
) -> None:
```

**After:**
```python
def save_duplicate_candidate(
    self,
    record_type: str,
    record1_id: UUID,
    record2_id: UUID,
    composite_score: float,  # NEW PARAMETER
    scores: dict,
    method: str = 'auto'
) -> None:
```

#### 2. Removed Incorrect Recalculation (Lines 1059-1065)

**Before:**
```python
# Calculate composite score
composite_score = (
    self.WEIGHT_VECTOR * scores['vector_sim'] +
    self.WEIGHT_PHONETIC * scores['phonetic_sim'] +
    self.WEIGHT_DATE * scores['date_sim'] +
    self.WEIGHT_LOCATION * scores['location_sim']
)

# Create new candidate
```

**After:**
```python
# Create new candidate (composite_score already calculated correctly by caller)
```

#### 3. Updated All Callers

Updated 4 methods to pass the composite_score parameter:

1. **[`detect_person_duplicates()`](src/app/services/duplicate_detector.py:173)** (Line 173)
2. **[`detect_baptism_duplicates()`](src/app/services/duplicate_detector.py:260)** (Line 260)
3. **[`detect_marriage_duplicates()`](src/app/services/duplicate_detector.py:347)** (Line 347)
4. **[`detect_death_duplicates()`](src/app/services/duplicate_detector.py:434)** (Line 434)

**Example Change:**
```python
# Before:
self.save_duplicate_candidate(
    'person',
    person.id,
    candidate_person.id,
    score_breakdown,  # scores dict only
    method='auto'
)

# After:
self.save_duplicate_candidate(
    'person',
    person.id,
    candidate_person.id,
    composite_score,  # ADD: the calculated score
    score_breakdown,  # scores dict
    method='auto'
)
```

## Verification

### Test Results

The fix was verified using [`test_missing_data_masking.py`](test_missing_data_masking.py):

```
[Test 2] Record 2 missing location data:
  Vector similarity: 0.95
  Phonetic similarity: 1.0
  Date similarity: 1.0
  Location similarity: None  ✓ Correctly stored as None
  Composite score: 0.978     ✓ Correctly normalized

[Test 5] Both records missing all dates:
  Vector similarity: 0.95
  Phonetic similarity: 1.0
  Date similarity: None      ✓ Correctly stored as None
  Location similarity: 1.0
  Composite score: 0.975     ✓ Correctly normalized
```

### Key Improvements

1. **None values preserved**: Component scores are now correctly stored as `None` when masked
2. **Correct normalization**: Composite scores are calculated with proper weight normalization
3. **Mathematical consistency**: No more impossible score combinations
4. **Single source of truth**: Composite score calculation happens only in [`calculate_composite_score()`](src/app/services/duplicate_detector.py:453)

## Files Modified

- [`src/app/services/duplicate_detector.py`](src/app/services/duplicate_detector.py)
  - Line 1003: Updated `save_duplicate_candidate()` signature
  - Lines 1059-1065: Removed incorrect recalculation
  - Line 173: Updated `detect_person_duplicates()` caller
  - Line 260: Updated `detect_baptism_duplicates()` caller
  - Line 347: Updated `detect_marriage_duplicates()` caller
  - Line 434: Updated `detect_death_duplicates()` caller

## Impact

- **Duplicate detection accuracy**: Significantly improved for records with missing optional data
- **Score consistency**: Composite scores now match the values returned by detection methods
- **Data integrity**: Component scores correctly reflect missing data with `None` values
- **Backward compatibility**: No changes to public API or database schema

## Related Documentation

- [`GEDCOM_DUPLICATE_DETECTION.md`](GEDCOM_DUPLICATE_DETECTION.md) - Duplicate detection system overview
- [`test_missing_data_masking.py`](test_missing_data_masking.py) - Test suite for missing data handling
