# Langfuse Integration Refactoring Summary

## Overview
This document summarizes the Langfuse integration refactoring completed for the GEDCOM generation microservice. The refactoring adds comprehensive tracing for document group processing, error logging throughout the pipeline, and detailed entity count metrics.

## Changes Made

### 1. Enhanced Langfuse Tracer Utility (`src/utils/langfuse_tracer.py`)

#### New Functions Added:

**`create_span(name, metadata)`** - Context manager for manual span creation
- Creates Langfuse spans for tracking specific operations
- Accepts metadata dictionary for rich context
- Gracefully handles cases where Langfuse is unavailable
- Returns span context that can be used to update the span

**`log_error(error, context, level)`** - Error logging to Langfuse
- Captures exception details, stack traces, and context
- Supports different error levels (ERROR, WARNING, etc.)
- Automatically extracts error type and message
- Associates errors with current observation/span
- Includes optional context dictionary for debugging

#### Example Usage:
```python
# Create a span with metadata
with langfuse_tracer.create_span("process-document-group", metadata={"document_id": doc_id}):
    # Your processing code here
    pass

# Log an error with context
try:
    # Some operation
    pass
except Exception as e:
    langfuse_tracer.log_error(
        e,
        context={"document_id": doc_id, "operation": "gedcom_generation"}
    )
    raise
```

### 2. Document Group Spans (`src/main.py`)

#### Added to `process_complete_document()`:

**Decorator**: Added `@langfuse_tracer.observe(name="process-document-group")` to the function

**Span Metadata**: Created comprehensive metadata for each document group:
- `document_id`: Unique identifier for the document
- `num_pages`: Number of pages in the group
- `expected_pages`: Expected total pages
- `completion_reason`: Why processing started (all_pages_received, timeout_reached)
- `document_title`: Title from metadata
- `location`: Location from metadata
- `date_range`: Date range from metadata
- `page_numbers_received`: List of actual page numbers received

**Nested Span**: Used `create_span()` to create an inner span with all the metadata

#### Example Trace Hierarchy:
```
process-document-group (outer span from @observe)
└── process-document-group (inner span with metadata)
    ├── gedcom-generation
    │   └── openrouter-llm-call
    └── [error logs if any occur]
```

### 3. Error Logging Implementation

#### Locations Where Error Logging Was Added:

**`src/main.py` - `process_complete_document()`**:
- Document group not found
- Missing pages warning
- GEDCOM generation failures
- GEDCOM validation failures
- S3 upload failures
- SQS publish failures
- Top-level processing errors

**`src/services/gedcom_generator.py` - `generate_from_document_group()`**:
- Document formatting errors
- OpenRouter API call failures
- General GEDCOM generation errors

**`src/services/openrouter_client.py` - `generate_gedcom()`**:
- Rate limit errors (with retry context)
- API timeout errors (with retry context)
- General API errors (with retry context)
- Response parsing errors

**`src/services/document_grouper.py` - `add_message()`**:
- Missing document_id errors
- Message addition failures
- Redis lock acquisition warnings
- Redis operation failures

#### Error Context Examples:

**Missing Pages Warning**:
```python
langfuse_tracer.log_error(
    ValueError(f"Missing pages: {sorted(missing)}"),
    context={
        "document_id": document_id,
        "operation": "page_completeness_check",
        "missing_pages": sorted(missing),
        "expected_pages": group.expected_pages,
        "received_pages": sorted(received)
    },
    level="WARNING"
)
```

**API Retry Error**:
```python
langfuse_tracer.log_error(
    e,
    context={
        "operation": "openrouter_api_call",
        "error_type": "rate_limit",
        "attempt": attempt + 1,
        "max_retries": self.max_retries,
        "retry_wait_seconds": wait_time,
        "model": self.model
    },
    level="WARNING"
)
```

## Files Modified

1. **`src/utils/langfuse_tracer.py`**
   - Added `create_span()` context manager
   - Added `log_error()` function
   - Imported `langfuse_context` for span updates
   - Added no-op implementations for when Langfuse is unavailable

2. **`src/main.py`**
   - Added `@observe` decorator to `process_complete_document()`
   - Created document group span with comprehensive metadata
   - Added error logging for all critical operations
   - Wrapped operations in try-except blocks with Langfuse error logging

3. **`src/services/gedcom_generator.py`**
   - Added error logging for document formatting failures
   - Added error logging for OpenRouter API call failures
   - Added error logging for general generation errors

4. **`src/services/openrouter_client.py`**
   - Added error logging for rate limit errors
   - Added error logging for timeout errors
   - Added error logging for API errors
   - Added error logging for parsing errors
   - Included retry context in warning-level logs

5. **`src/services/document_grouper.py`**
   - Added error logging for missing document_id
   - Added error logging for message addition failures
   - Added warning-level logging for Redis lock issues
   - Added error logging for Redis operation failures

## Testing

Created comprehensive test suite: `test_langfuse_refactoring.py`

### Test Coverage:
- ✅ Span creation with metadata
- ✅ Error logging with context
- ✅ Error logging with different levels (ERROR, WARNING)
- ✅ DocumentGrouper error handling
- ✅ Traced functions with error logging
- ✅ Nested spans
- ✅ Graceful handling when Langfuse is unavailable

### Test Results:
All tests pass successfully, both with and without Langfuse installed.

## Entity Count Metrics

The system now tracks comprehensive entity counts as Langfuse scores:

### Scores Added:
1. **`total_persons`** - Total number of individuals/persons in the GEDCOM
2. **`individuals_processed`** - Number of INDI records processed
3. **`families_processed`** - Number of FAM records processed
4. **`baptisms_processed`** - Number of baptism events (BAPM/CHR tags)
5. **`deaths_processed`** - Number of death events (DEAT tags)
6. **`marriages_processed`** - Number of marriage events (MARR tags)
7. **`total_events`** - Sum of all events (baptisms + deaths + marriages)

### Implementation:
- Enhanced [`count_gedcom_records()`](gedcom-generation-microservice/src/services/gedcom_generator.py:138) to count all entity types
- Added Langfuse scores for each metric in [`process_complete_document()`](gedcom-generation-microservice/src/main.py:249)
- Included all counts in the GEDCOM ready message for downstream processing

## Tracing Structure Example

When processing a document group, the following trace structure is created in Langfuse:

```
process-document-group
├── metadata:
│   ├── document_id: "doc-123"
│   ├── num_pages: 5
│   ├── expected_pages: 5
│   ├── completion_reason: "all_pages_received"
│   ├── document_title: "Birth Records 1900-1910"
│   ├── location: "Warsaw, Poland"
│   ├── date_range: "1900-1910"
│   └── page_numbers_received: [1, 2, 3, 4, 5]
├── scores:
│   ├── total_persons: 45
│   ├── individuals_processed: 45
│   ├── families_processed: 12
│   ├── baptisms_processed: 38
│   ├── deaths_processed: 15
│   ├── marriages_processed: 10
│   └── total_events: 63
├── gedcom-generation
│   ├── openrouter-llm-call (generation)
│   │   ├── input: formatted document
│   │   ├── output: GEDCOM content
│   │   └── metadata: token usage, model, etc.
│   └── [errors if any]
└── [errors if any]
```

## Error Tracking Benefits

1. **Complete Context**: Every error includes relevant context (document_id, operation, etc.)
2. **Stack Traces**: Full stack traces are captured automatically
3. **Error Levels**: Warnings vs. errors are properly distinguished
4. **Retry Information**: Retry attempts and backoff times are logged
5. **Debugging**: Easy to identify which operation failed and why
6. **Monitoring**: Can track error rates and patterns in Langfuse dashboard

## Graceful Degradation

The implementation gracefully handles cases where Langfuse is unavailable:
- No-op decorators and functions are provided
- No exceptions are raised if Langfuse fails
- Main workflow continues uninterrupted
- Errors are still logged to standard logger

## Usage in Production

To enable Langfuse tracing in production:

1. Install Langfuse: `pip install langfuse`
2. Set environment variables:
   ```bash
   LANGFUSE_PUBLIC_KEY=pk-...
   LANGFUSE_SECRET_KEY=sk-...
   LANGFUSE_HOST=https://cloud.langfuse.com  # optional
   ```
3. Run the service normally - tracing happens automatically

## Monitoring Recommendations

In the Langfuse dashboard, you can now:

1. **Track Document Processing**:
   - View all document groups processed
   - See completion reasons (all pages vs. timeout)
   - Monitor page counts and missing pages

2. **Monitor Entity Metrics**:
   - Track total persons/individuals processed
   - Monitor family records created
   - View baptism, death, and marriage event counts
   - Analyze total events per document
   - Compare entity counts across documents
   - Identify documents with unusual entity distributions

3. **Monitor Errors**:
   - Filter by error type (rate_limit, timeout, api_error, etc.)
   - View error context and stack traces
   - Track error rates over time

4. **Analyze Performance**:
   - See processing time for each document group
   - Monitor LLM token usage
   - Track retry patterns
   - Correlate entity counts with processing time

5. **Debug Issues**:
   - Search by document_id to see full trace
   - View nested span hierarchy
   - Examine error context for failed operations
   - Check entity counts to verify extraction quality

## Future Enhancements

Potential improvements for future iterations:

1. Add spans for individual page processing
2. Track metadata extraction performance
3. Add custom metrics for GEDCOM quality (e.g., completeness scores)
4. Implement distributed tracing across microservices
5. Add user-level tracing for multi-tenant scenarios
6. Track entity extraction accuracy metrics
7. Add alerts for unusual entity count patterns

## Conclusion

This refactoring provides comprehensive observability for the GEDCOM generation pipeline:
- ✅ Document group spans with rich metadata
- ✅ Error logging throughout the pipeline
- ✅ Proper error context and stack traces
- ✅ Graceful handling of Langfuse unavailability
- ✅ Maintains existing tracing patterns
- ✅ No breaking changes to existing functionality

The implementation follows best practices for observability and makes debugging production issues significantly easier.
