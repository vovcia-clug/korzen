# Langfuse API Fix Documentation

## Problem

The gedcom-generation-microservice was experiencing an `AttributeError` when trying to use Langfuse tracing:

```
Error creating Langfuse trace: 'Langfuse' object has no attribute 'trace'
```

## Root Cause

The code in [`langfuse_tracer.py`](src/utils/langfuse_tracer.py) was using an incorrect API pattern for the Langfuse Python SDK v2.0+:

```python
# INCORRECT - This doesn't exist in Langfuse SDK
trace = _langfuse_client.trace(
    name=name,
    input=input_data,
    ...
)
```

The `Langfuse` client object does **not** have a `trace()` method. This was a misunderstanding of the Langfuse SDK API.

## Solution

The Langfuse Python SDK v2.0+ uses **Static Client classes** for manual tracing:

- `StaticTraceClient` - for creating traces
- `StaticSpanClient` - for creating spans within traces
- `StaticGenerationClient` - for creating LLM generation observations

### Changes Made

1. **Import Static Client classes** in [`langfuse_tracer.py:38-40`](src/utils/langfuse_tracer.py:38):
   ```python
   from langfuse.client import StaticTraceClient, StaticSpanClient, StaticGenerationClient
   ```

2. **Updated `trace_context()` function** to use `StaticTraceClient`:
   ```python
   trace = StaticTraceClient(
       client=_langfuse_client,
       name=name,
       input=input_data,
       metadata=metadata,
       tags=tags,
       user_id=user_id,
       session_id=session_id
   )
   ```

3. **Updated `span_context()` function** to use `StaticSpanClient`:
   ```python
   span = StaticSpanClient(
       client=_langfuse_client,
       trace_id=trace.trace_id,
       name=name,
       input=input_data,
       metadata=metadata
   )
   ```

4. **Updated `generation_context()` function** to use `StaticGenerationClient`:
   ```python
   generation = StaticGenerationClient(
       client=_langfuse_client,
       trace_id=trace.trace_id,
       name=name,
       model=model,
       input=input_data,
       metadata=metadata,
       model_parameters=model_parameters
   )
   ```

## API Pattern Comparison

### Before (Incorrect)
```python
# This API doesn't exist
trace = langfuse_client.trace(...)
span = trace.span(...)
generation = trace.generation(...)
```

### After (Correct)
```python
# Correct Langfuse SDK v2.0+ API
from langfuse.client import StaticTraceClient, StaticSpanClient, StaticGenerationClient

trace = StaticTraceClient(client=langfuse_client, ...)
span = StaticSpanClient(client=langfuse_client, trace_id=trace.trace_id, ...)
generation = StaticGenerationClient(client=langfuse_client, trace_id=trace.trace_id, ...)
```

## Alternative Approach

For simpler use cases, Langfuse also provides the `@observe()` decorator which handles tracing automatically:

```python
from langfuse.decorators import observe

@observe()
def my_function():
    # Automatically traced
    pass
```

However, the current implementation uses manual tracing with context managers for more fine-grained control, which is appropriate for this microservice's needs.

## Testing

The fix has been validated to:
1. ✓ Use the correct Langfuse SDK API structure
2. ✓ Import the correct Static Client classes
3. ✓ Pass trace_id correctly between parent and child observations
4. ✓ Maintain backward compatibility (gracefully degrades when Langfuse is not configured)

## Files Modified

- [`gedcom-generation-microservice/src/utils/langfuse_tracer.py`](src/utils/langfuse_tracer.py) - Core tracing utilities

## Files Using Tracing (No Changes Needed)

The following files use the tracing utilities correctly via context managers and require no changes:

- [`gedcom-generation-microservice/src/main.py`](src/main.py) - Main service with trace contexts
- [`gedcom-generation-microservice/src/services/gedcom_generator.py`](src/services/gedcom_generator.py) - GEDCOM generation with spans
- [`gedcom-generation-microservice/src/services/openrouter_client.py`](src/services/openrouter_client.py) - LLM calls with generation contexts
- [`gedcom-generation-microservice/src/services/document_grouper.py`](src/services/document_grouper.py) - Document grouping with spans

## References

- Langfuse Python SDK Documentation: https://langfuse.com/docs/sdk/python
- Langfuse Tracing Guide: https://langfuse.com/docs/tracing
- Static Client API: https://langfuse.com/docs/sdk/python/low-level-sdk

## Date

Fixed: 2026-05-23
