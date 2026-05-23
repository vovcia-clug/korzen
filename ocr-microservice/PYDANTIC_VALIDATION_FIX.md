# Pydantic Validation Error Fix

## Problem
The OpenRouter LLM was returning JSON that didn't match the Pydantic model schema, causing 60 validation errors:
```
Field required [type=missing, input_value={'given_names': '...', 'surname': '...', ...}, input_type=dict]
```

All errors indicated that `name` field was missing from `person`, `parents`, and `witnesses` objects.

## Root Cause
**Schema Mismatch between Prompt and Pydantic Models**

The prompt in `src/prompts/church_records_extraction.py` (lines 171-196) instructed the LLM to return:
```json
"person": {
  "given_names": "...",
  "surname": "...",
  "full_name": "..."
}
```

But the Pydantic models expected:
```json
"person": {
  "name": {
    "given_names": "...",
    "surname": "...",
    "full_name": "..."
  }
}
```

## Solution
Updated Pydantic models to match the prompt structure (flattening the nested `PersonName` object).

### Files Changed

#### 1. `src/models/person_record.py`
- **Removed**: `PersonName` class (nested name structure)
- **Updated**: `PersonRecord`, `ParentRecord`, and `WitnessRecord` to have flat structure with `given_names`, `surname`, and `full_name` as direct attributes

**Before:**
```python
class PersonName(BaseModel):
    given_names: str
    surname: str
    full_name: str

class PersonRecord(BaseModel):
    name: PersonName  # Nested structure
    gender: Optional[str] = None
    ...
```

**After:**
```python
class PersonRecord(BaseModel):
    given_names: str  # Flat structure
    surname: str
    full_name: str
    gender: Optional[str] = None
    ...
```

#### 2. `src/models/__init__.py`
- Removed `PersonName` from exports

#### 3. `src/services/church_records_parser.py`
- Updated imports to remove `PersonName` and add `PersonRecord`, `ParentRecord`, `WitnessRecord`
- Updated `_normalize_name()` method signature from:
  ```python
  def _normalize_name(self, name: PersonName) -> Tuple[str, str]:
      given_names = unidecode(name.given_names.strip())
      surname = unidecode(name.surname.strip())
  ```
  To:
  ```python
  def _normalize_name(self, record: Union[PersonRecord, ParentRecord, WitnessRecord]) -> Tuple[str, str]:
      given_names = unidecode(record.given_names.strip())
      surname = unidecode(record.surname.strip())
  ```
- Updated all calls to `_normalize_name()` from:
  - `self._normalize_name(event.person.name)` → `self._normalize_name(event.person)`
  - `self._normalize_name(parent.name)` → `self._normalize_name(parent)`
  - `self._normalize_name(event.spouse.name)` → `self._normalize_name(event.spouse)`

#### 4. `src/services/openrouter_client.py`
- Added diagnostic logging to help identify future schema mismatches

## Testing
The fix ensures that the Pydantic models now match the exact structure the LLM returns based on the prompt instructions:

```python
# This structure will now validate successfully:
{
  "records": [{
    "person": {
      "given_names": "Vincentius",
      "surname": "Kowalski",
      "full_name": "Vincentius Kowalski"
    },
    "parents": [{
      "given_names": "Jan",
      "surname": "Kowalski",
      "full_name": "Jan Kowalski",
      "role": "father"
    }],
    "witnesses": [{
      "given_names": "Maria",
      "surname": "Nowak",
      "full_name": "Maria Nowak",
      "role": "godmother"
    }]
  }]
}
```

## Why Flatten Instead of Updating Prompt?
1. The prompt is detailed and carefully crafted with examples
2. Changing the prompt could affect LLM behavior and accuracy
3. The flat structure is simpler and matches the prompt examples
4. Less risk of breaking the extraction quality

## Verification
To verify the fix works, run the OCR microservice and process a message. The validation errors should no longer occur.
