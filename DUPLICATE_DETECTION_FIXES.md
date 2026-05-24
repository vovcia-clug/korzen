# Duplicate Detection False Positive Fixes

## Overview

This document describes the 5 critical fixes implemented to resolve false positive auto-merges in the duplicate detection system. These fixes address the issues that caused incorrect matches like "Ethel Houston" → "Adele None" and "Otto L. Loesch" → "Adele None".

## Implemented Fixes

### Fix 1: Corrected Auto-Merge Threshold (100% Match Only)

**File:** [`src/app/gedcom_constants.py`](src/app/gedcom_constants.py:50)

**Change:**
```python
# Before
AUTO_MERGE_THRESHOLD = 0.95  # Only auto-merge at 100% similarity

# After
AUTO_MERGE_THRESHOLD = 1.0  # Only auto-merge at 100% similarity (true perfect match)
```

**Impact:** 
- Previously, any match scoring ≥94.99% was auto-merged (due to tolerance in comparison logic)
- Now requires true 100% similarity for auto-merge
- Prevents near-matches from being automatically merged without review

---

### Fix 2: Stricter Data Validation Requirements

**File:** [`src/app/services/duplicate_detector.py`](src/app/services/duplicate_detector.py:101-159)

**Change:** Updated `_should_skip_person_duplicate_detection()` method to require:
- **Surname** (last_name or maiden_name), OR
- **Both dates AND locations** together

**Before:** Only skipped persons with ONLY a first name and no other data
**After:** Skips persons lacking surname AND lacking (dates AND locations)

**Impact:**
- Prevents records like "Adele None" (first name + birth year only) from entering duplicate detection
- Reduces false positives from generic first names matching broadly
- Requires sufficient identifying information before processing

**Example:**
```python
# Now SKIPPED (insufficient data):
Person(first_name="Adele", birth_date="1850-01-01")  # No surname, no location

# Still PROCESSED (sufficient data):
Person(first_name="Jan", last_name="Kowalski")  # Has surname
Person(first_name="Maria", birth_date="1850-01-01", birth_place="Krakow")  # Has dates AND locations
```

---

### Fix 3: Gender Validation (Instant Rejection)

**File:** [`src/app/services/duplicate_detector.py`](src/app/services/duplicate_detector.py:578-593)

**Change:** Added gender mismatch detection at the start of `calculate_composite_score()`

```python
# For person records, check gender mismatch
if record_type == 'person':
    if record1.gender and record2.gender:
        if record1.gender != record2.gender:
            return 0.0, {
                'vector_sim': vector_sim,
                'phonetic_sim': None,
                'date_sim': None,
                'location_sim': None,
                'rejection_reason': 'gender_mismatch'
            }
```

**Impact:**
- Prevents male-female matches (e.g., "Otto L. Loesch" → "Adele None")
- Instant rejection with 0.0 score when genders differ
- No computational waste on obviously incorrect matches

---

### Fix 4: Penalize Missing Data (No More Rewards)

**File:** [`src/app/services/duplicate_detector.py`](src/app/services/duplicate_detector.py:594-640)

**Change:** Replaced dynamic weight normalization with fixed weights and missing data penalty

**Before (Dynamic Normalization):**
```python
# Only included components with data, normalized by actual weights used
if phonetic_sim is not None:
    composite_score += WEIGHT_PHONETIC * phonetic_sim
    total_weight += WEIGHT_PHONETIC

composite_score = composite_score / total_weight  # Rewards missing data!
```

**After (Fixed Weights with Penalty):**
```python
MISSING_DATA_PENALTY = 0.3  # Score assigned when data is missing

# Always use all weights, assign penalty for missing components
if phonetic_sim is not None:
    composite_score += WEIGHT_PHONETIC * phonetic_sim
else:
    composite_score += WEIGHT_PHONETIC * MISSING_DATA_PENALTY

# No normalization - weights sum to 1.0
```

**Impact:**
- Missing data now **lowers** the score instead of being ignored
- Records with complete data score higher than incomplete records
- Prevents artificially high scores for records with minimal information

**Example Calculation:**

**Before (Dynamic):**
- Vector: 0.92 (40% weight)
- Phonetic: Missing (30% weight skipped)
- Date: Missing (20% weight skipped)
- Location: Missing (10% weight skipped)
- **Score:** 0.92 / 0.40 = **0.92** (artificially high!)

**After (Fixed with Penalty):**
- Vector: 0.92 × 0.40 = 0.368
- Phonetic: 0.30 × 0.40 = 0.120 (penalty)
- Date: 0.30 × 0.20 = 0.060 (penalty)
- Location: 0.30 × 0.10 = 0.030 (penalty)
- **Score:** 0.368 + 0.120 + 0.060 + 0.030 = **0.578** (realistic!)

---

### Fix 5: Increased Phonetic Embedding Dimensions

**File:** [`src/app/services/embedding_generator.py`](src/app/services/embedding_generator.py:68-72)

**Change:** Increased phonetic dimensions from 32 to 64 to reduce hash collisions

```python
# Before
PHONETIC_DIM = 32
TEMPORAL_DIM = 16
LOCATION_DIM = 80
TOTAL_DIM = 128

# After
PHONETIC_DIM = 64  # Increased from 32 to reduce hash collisions
TEMPORAL_DIM = 16
LOCATION_DIM = 48  # Reduced from 80 to maintain TOTAL_DIM = 128
TOTAL_DIM = 128
```

**Impact:**
- Reduces hash collisions for common names (Maria, Jan, Adele, etc.)
- Improves discrimination between similar phonetic codes
- Better name-based duplicate detection accuracy
- Maintains 128-dimensional embedding for database compatibility

**Technical Details:**
- Hash-based encoding uses MD5 with modulo operations
- More dimensions = less collision probability
- Common names now produce more distinct embeddings

---

## Expected Results

After these fixes, the duplicate detection system should:

1. ✅ **Only auto-merge at 100% similarity** (not 95%)
2. ✅ **Skip records with insufficient data** (no surname and no dates+locations)
3. ✅ **Reject gender mismatches instantly** (no male-female matches)
4. ✅ **Penalize incomplete records** (lower scores for missing data)
5. ✅ **Better distinguish common names** (reduced hash collisions)

## Testing Recommendations

To verify the fixes work correctly:

1. **Re-import GEDCOM files** to regenerate embeddings with new 64-dimensional phonetic encoding
2. **Run duplicate detection** on the same dataset that produced false positives
3. **Verify no gender mismatches** appear in results
4. **Check that records like "Adele None"** are skipped during detection
5. **Confirm auto-merge threshold** only triggers at 100% similarity

## Database Considerations

**Important:** The embedding dimension change (Fix 5) requires:
- Existing embeddings remain valid (still 128 dimensions)
- New embeddings will have different phonetic/location distribution
- Consider regenerating all embeddings for consistency
- No database schema changes needed (vector column already supports 128 dimensions)

## Files Modified

1. [`src/app/gedcom_constants.py`](src/app/gedcom_constants.py) - Auto-merge threshold
2. [`src/app/services/duplicate_detector.py`](src/app/services/duplicate_detector.py) - Validation, gender check, missing data penalty
3. [`src/app/services/embedding_generator.py`](src/app/services/embedding_generator.py) - Embedding dimensions

## Summary

These fixes address the root causes of false positive matches by:
- Enforcing stricter matching thresholds
- Requiring sufficient identifying information
- Validating gender consistency
- Properly penalizing missing data
- Improving phonetic encoding quality

The system should now produce significantly fewer false positives while maintaining high recall for true duplicates.
