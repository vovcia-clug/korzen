# Langfuse Score Metrics Implementation

This document describes the Langfuse score metrics implementation for tracking individuals and families processed in the GEDCOM generation microservice.

## Overview

Score metrics have been added to track key performance indicators (KPIs) for GEDCOM generation:
- **`individuals_processed`**: Number of individuals (INDI records) in generated GEDCOM
- **`families_processed`**: Number of families (FAM records) in generated GEDCOM

These metrics are automatically attached to Langfuse traces and can be viewed in the Langfuse dashboard for monitoring and analytics.

## Implementation Details

### 1. Score Function Added to `langfuse_tracer.py`

A new [`add_score()`](src/utils/langfuse_tracer.py:60) function was added to the Langfuse tracer utility:

```python
def add_score(name: str, value: float, comment: Optional[str] = None) -> None:
    """
    Add a score to the current trace.
    
    Args:
        name: Name of the score metric
        value: Numeric value of the score
        comment: Optional comment describing the score
    """
```

**Features:**
- Uses Langfuse client's `score_current_trace()` method
- Gracefully handles cases where Langfuse is not configured
- Logs debug messages for tracking
- Supports optional comments for context

### 2. Score Metrics in `main.py`

Score metrics are added in the [`process_complete_document()`](src/main.py:154) method after GEDCOM generation and counting:

**Location:** [`main.py:213-223`](src/main.py:213)

```python
# Count records
record_counts = self.gedcom_generator.count_gedcom_records(gedcom_content)

# Add Langfuse score metrics for tracking
langfuse_tracer.add_score(
    name="individuals_processed",
    value=record_counts["individuals"],
    comment=f"Number of individuals processed in document {document_id}"
)
langfuse_tracer.add_score(
    name="families_processed",
    value=record_counts["families"],
    comment=f"Number of families processed in document {document_id}"
)
```

### 3. Record Counting Logic

The existing [`count_gedcom_records()`](src/services/gedcom_generator.py:104) method in [`gedcom_generator.py`](src/services/gedcom_generator.py:104) counts records by parsing GEDCOM content:

```python
def count_gedcom_records(self, gedcom_content: str) -> dict:
    """
    Count individuals and families in GEDCOM content.
    
    Returns:
        Dictionary with counts: {individuals, families}
    """
    lines = gedcom_content.split('\n')
    
    individual_count = 0
    family_count = 0
    
    for line in lines:
        if line.startswith('0 @I') and '@ INDI' in line:
            individual_count += 1
        elif line.startswith('0 @F') and '@ FAM' in line:
            family_count += 1
    
    return {
        "individuals": individual_count,
        "families": family_count
    }
```

## Trace Hierarchy

Scores are attached to the top-level trace for each document processing operation:

```
process-sqs-message (trace) ← Scores attached here
├── group-document (span)
└── process-complete-document (span)
    ├── gedcom-generation (span)
    │   ├── format-document (span)
    │   └── openrouter-llm-call (generation)
    ├── validate-gedcom (span)
    ├── upload-to-s3 (span)
    └── publish-to-sqs (span)
```

**Scores:**
- `individuals_processed`: Count of INDI records
- `families_processed`: Count of FAM records

## Viewing Metrics in Langfuse

### In the Langfuse Dashboard

1. **Traces View**
   - Navigate to the Traces section
   - Click on any trace for a processed document
   - Scroll to the "Scores" section
   - View `individuals_processed` and `families_processed` metrics

2. **Sessions View**
   - Group traces by `session_id` (document_id)
   - See aggregate scores across all operations for a document

3. **Analytics**
   - Create custom dashboards to track:
     - Average individuals per document
     - Average families per document
     - Total records processed over time
     - Processing trends and patterns

### Score Attributes

Each score includes:
- **Name**: `individuals_processed` or `families_processed`
- **Value**: Numeric count (integer)
- **Comment**: Contextual information (e.g., "Number of individuals processed in document doc-123")
- **Timestamp**: When the score was recorded
- **Trace ID**: Associated trace for correlation

## Usage Examples

### Basic Usage

The scores are automatically added during normal microservice operation. No additional configuration is needed beyond setting up Langfuse credentials.

### Manual Score Addition

You can add custom scores in any `@observe` decorated function:

```python
from utils import langfuse_tracer

@langfuse_tracer.observe(name="custom-operation")
async def custom_operation():
    # Your processing logic
    result = process_data()
    
    # Add custom score
    langfuse_tracer.add_score(
        name="custom_metric",
        value=result.count,
        comment="Custom metric description"
    )
    
    return result
```

## Testing

### Run the Test Suite

```bash
cd gedcom-generation-microservice
. ~/venv/bin/activate
python test_score_simple.py
```

The test suite verifies:
- ✅ Score function works correctly
- ✅ GEDCOM counting logic is accurate
- ✅ Scores integrate with `@observe` decorator
- ✅ Graceful degradation when Langfuse is not configured

### Expected Output

```
============================================================
Langfuse Score Metrics - Simple Test
============================================================

=== Testing Basic Score Functionality ===
✓ Langfuse available: True
✓ Testing add_score() function...
  ✓ individuals_processed score added successfully
  ✓ families_processed score added successfully
  ✓ Score without comment added successfully

✅ All basic score tests passed!

=== Testing GEDCOM Counting Logic ===
✓ Counted 3 individuals
✓ Counted 2 families
  ✓ Counts are correct!
  ✓ Scores added for counted records

✅ GEDCOM counting test passed!

=== Testing Scores with @observe Decorator ===
✓ Calling @observe decorated function...
  Result: {'individuals': 15, 'families': 7}
  ✓ Function executed successfully with scores

✅ Decorator integration test passed!

============================================================
✅ ALL TESTS PASSED!
============================================================
```

## Configuration

### Environment Variables

Scores work automatically when Langfuse is configured:

```bash
# Required for Langfuse (including scores)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Graceful Degradation

If Langfuse is not configured:
- Score operations become no-ops
- No errors or warnings
- Service continues to work normally
- No performance impact

## Benefits

### 1. **Monitoring**
- Track processing volume over time
- Identify trends in document complexity
- Monitor service throughput

### 2. **Analytics**
- Calculate average records per document
- Identify outliers (unusually large/small documents)
- Measure processing efficiency

### 3. **Debugging**
- Correlate errors with document size
- Identify performance bottlenecks
- Validate processing completeness

### 4. **Business Intelligence**
- Report on total records processed
- Track service usage patterns
- Measure value delivered to users

## Best Practices

### 1. Use Descriptive Names
```python
# ✓ Good - clear and specific
langfuse_tracer.add_score(name="individuals_processed", value=10)

# ✗ Bad - too generic
langfuse_tracer.add_score(name="count", value=10)
```

### 2. Add Contextual Comments
```python
# ✓ Good - provides context
langfuse_tracer.add_score(
    name="individuals_processed",
    value=10,
    comment=f"Processed from document {document_id}"
)

# ✗ Bad - no context
langfuse_tracer.add_score(name="individuals_processed", value=10)
```

### 3. Use Numeric Values
```python
# ✓ Good - numeric values for aggregation
langfuse_tracer.add_score(name="individuals_processed", value=10)

# ✗ Bad - string values can't be aggregated
langfuse_tracer.add_score(name="individuals_processed", value="10")
```

### 4. Score at Appropriate Level
```python
# ✓ Good - score at trace level for document-wide metrics
@langfuse_tracer.observe(name="process-document")
async def process_document():
    result = generate_gedcom()
    langfuse_tracer.add_score(name="individuals_processed", value=result.count)
```

## Troubleshooting

### Scores Not Appearing

1. **Check Langfuse Configuration**
   ```bash
   python check_env.py
   ```

2. **Verify Scores Are Being Added**
   - Check logs for "Added score" debug messages
   - Ensure `count_gedcom_records()` returns valid counts

3. **Flush Traces**
   ```python
   langfuse_tracer.flush()  # Force send pending traces
   ```

4. **Check Langfuse Dashboard**
   - Ensure you're looking at the correct project
   - Check the time range filter
   - Verify trace exists before looking for scores

### Score Values Are Zero

1. **Verify GEDCOM Content**
   - Check that GEDCOM generation succeeded
   - Ensure GEDCOM contains INDI and FAM records

2. **Check Counting Logic**
   - Verify GEDCOM format matches expected patterns
   - Test with sample GEDCOM files

## Future Enhancements

Potential additional metrics to track:
- `pages_processed`: Number of pages in source document
- `processing_time_ms`: Time taken to generate GEDCOM
- `validation_errors`: Number of validation errors
- `llm_tokens_used`: Total tokens consumed
- `retry_count`: Number of retries needed

## References

- [Langfuse Scores Documentation](https://langfuse.com/docs/scores)
- [Langfuse Python SDK](https://langfuse.com/docs/sdk/python)
- [Main Tracing Documentation](LANGFUSE_TRACING.md)
- [GEDCOM Generator Service](src/services/gedcom_generator.py)
- [Main Service Implementation](src/main.py)

## Summary

Score metrics provide valuable insights into GEDCOM generation performance and volume. The implementation:

✅ **Tracks key metrics**: individuals and families processed  
✅ **Integrates seamlessly**: Works with existing `@observe` decorators  
✅ **Gracefully degrades**: No errors when Langfuse is not configured  
✅ **Well tested**: Comprehensive test suite included  
✅ **Easy to extend**: Simple API for adding custom metrics  

The metrics are now automatically tracked for every document processed by the microservice and can be viewed in the Langfuse dashboard for monitoring and analytics.
