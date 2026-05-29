# Langfuse Model Name Tracking Fix

## Problem

Langfuse was not receiving the model name when tracking LLM API calls. The `@observe` decorator with `as_type="generation"` was being used, but the model information was not being passed to Langfuse, resulting in missing model names in the Langfuse UI.

## Root Cause

The Langfuse v4.x API requires explicit calls to `langfuse_context.update_current_observation()` to pass model information to observations. Simply using the `@observe` decorator is not sufficient - you must manually update the observation with model details.

## Solution

### 1. Enhanced `langfuse_tracer.py`

Added helper functions to properly interact with Langfuse v4.x context API:

- **`update_current_observation(**kwargs)`** - Updates the current observation with model info, usage, etc.
- **`update_current_trace(**kwargs)`** - Updates the current trace with session_id, tags, metadata
- Imported `langfuse_context` from `langfuse.decorators`
- Added no-op implementations when Langfuse is not available

**Key changes:**
```python
from langfuse.decorators import langfuse_context

def update_current_observation(**kwargs) -> None:
    """Update the current observation with model info, usage, etc."""
    if _langfuse_available:
        try:
            langfuse_context.update_current_observation(**kwargs)
            logger.debug(f"Updated current observation with: {list(kwargs.keys())}")
        except Exception as e:
            logger.error(f"Error updating current observation: {e}")
```

### 2. Updated `openrouter_client.py`

Modified both `generate_gedcom()` and `generate_text()` methods to properly track model information:

**Before API call:**
```python
# Update Langfuse observation with model info before making the call
langfuse_tracer.update_current_observation(
    model=self.model,
    model_parameters={"temperature": 0.0},
    metadata={
        "operation": "gedcom_generation",
        "input_length": len(formatted_document)
    }
)
```

**After API call:**
```python
# Update Langfuse observation with usage info
if response.usage:
    langfuse_tracer.update_current_observation(
        usage={
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
            "total": response.usage.total_tokens
        }
    )
```

## What Gets Tracked

With this fix, Langfuse now properly tracks:

1. **Model Name** - e.g., `"google/gemini-flash-1.5"`
2. **Model Parameters** - e.g., `{"temperature": 0.0}`
3. **Token Usage** - Input, output, and total tokens
4. **Operation Metadata** - Operation type and input length
5. **Cost Calculation** - Langfuse automatically calculates costs based on model pricing

## Testing

Run the test suite to verify the fix:

```bash
cd gedcom-generation-microservice
. ~/venv/bin/activate
python test_model_tracking.py
```

The test verifies:
- ✓ Model name is correctly passed to Langfuse
- ✓ Model parameters are tracked
- ✓ Token usage is recorded
- ✓ Both `generate_gedcom()` and `generate_text()` methods work correctly

## Benefits

1. **Cost Tracking** - Langfuse can now calculate costs per model
2. **Model Comparison** - Compare performance across different models
3. **Usage Analytics** - Track token usage by model
4. **Debugging** - Easier to identify which model was used for each generation
5. **Compliance** - Better audit trail of model usage

## Usage Example

The fix is transparent to existing code. No changes needed in calling code:

```python
# This now automatically tracks model name in Langfuse
client = OpenRouterClient(
    api_key=api_key,
    model="google/gemini-flash-1.5"
)

gedcom = await client.generate_gedcom(
    formatted_document=doc,
    system_prompt=prompt
)
# Model name, parameters, and usage are now tracked in Langfuse!
```

## Langfuse UI

In the Langfuse UI, you'll now see:

- **Generations View**: Model name displayed for each generation
- **Cost Dashboard**: Accurate cost calculations per model
- **Token Usage**: Detailed breakdown by model
- **Model Comparison**: Compare performance metrics across models

## Related Files

- [`src/utils/langfuse_tracer.py`](src/utils/langfuse_tracer.py) - Enhanced with context helpers
- [`src/services/openrouter_client.py`](src/services/openrouter_client.py) - Updated to track model info
- [`test_model_tracking.py`](test_model_tracking.py) - Test suite for verification

## References

- [Langfuse Python SDK - Decorators](https://langfuse.com/docs/sdk/python/decorators)
- [Langfuse - Model Usage & Cost Tracking](https://langfuse.com/docs/model-usage-and-cost)
- [LANGFUSE_TRACING.md](LANGFUSE_TRACING.md) - General tracing documentation
