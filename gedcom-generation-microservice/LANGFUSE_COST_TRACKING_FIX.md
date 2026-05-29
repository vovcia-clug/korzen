# Langfuse Cost Tracking Fix

## Problem

Costs were not appearing in the Langfuse dashboard despite the Langfuse integration being properly configured and traces being sent successfully.

## Root Cause

The usage data was being sent to Langfuse with incorrect field names:

**Incorrect format (what we were sending):**
```python
usage_details = {
    "input": 100,
    "output": 50,
    "total": 150
}
```

**Correct format (what Langfuse v4.x expects):**
```python
usage_details = {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
}
```

According to the [Langfuse v4.x API documentation](https://langfuse.com/docs/model-usage-and-cost), the `usage_details` parameter for `update_current_generation()` expects the field names `prompt_tokens` and `completion_tokens`, not `input` and `output`.

This mismatch prevented Langfuse from:
- Recognizing the token usage data
- Calculating costs based on model pricing
- Displaying usage metrics in the dashboard

## Investigation Process

### 1. Examined the Code Flow

- [`openrouter_client.py`](src/services/openrouter_client.py) lines 148-155 and 369-376 send usage data as `{"input": X, "output": Y, "total": Z}`
- [`langfuse_tracer.py`](src/utils/langfuse_tracer.py) line 104 was directly passing this to `usage_details` without transformation
- Langfuse v4.x silently ignored the data because the field names didn't match

### 2. Verified Langfuse v4.x API

Checked the actual Langfuse v4.x SDK to confirm:
```python
# Method signature
update_current_generation(
    ...,
    usage_details: Optional[Dict[str, int]] = None,
    ...
)

# Documentation example
usage_details={
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens
}
```

### 3. Identified the Mismatch

The code was using generic names (`input`, `output`, `total`) instead of the OpenAI-standard names that Langfuse expects (`prompt_tokens`, `completion_tokens`, `total_tokens`).

## Solution

Updated [`langfuse_tracer.py`](src/utils/langfuse_tracer.py) line 100-104 to transform the usage data format:

```python
# Map 'usage' to 'usage_details' for generation
# Langfuse v4.x expects: prompt_tokens, completion_tokens, total_tokens
if 'usage' in kwargs:
    usage = kwargs['usage']
    # Transform from our format to Langfuse format
    if isinstance(usage, dict):
        usage_details = {}
        # Map 'input' -> 'prompt_tokens'
        if 'input' in usage:
            usage_details['prompt_tokens'] = usage['input']
        elif 'prompt_tokens' in usage:
            usage_details['prompt_tokens'] = usage['prompt_tokens']
        
        # Map 'output' -> 'completion_tokens'
        if 'output' in usage:
            usage_details['completion_tokens'] = usage['output']
        elif 'completion_tokens' in usage:
            usage_details['completion_tokens'] = usage['completion_tokens']
        
        # Map 'total' -> 'total_tokens' (optional)
        if 'total' in usage:
            usage_details['total_tokens'] = usage['total']
        elif 'total_tokens' in usage:
            usage_details['total_tokens'] = usage['total_tokens']
        
        generation_params['usage_details'] = usage_details
    else:
        generation_params['usage_details'] = usage
```

### Why This Approach?

1. **Backward Compatible** - Supports both the old format (`input`/`output`/`total`) and the correct format (`prompt_tokens`/`completion_tokens`/`total_tokens`)
2. **No Breaking Changes** - Existing code in `openrouter_client.py` doesn't need to be modified
3. **Centralized** - The transformation happens in one place (`langfuse_tracer.py`)
4. **Future-Proof** - If we later update `openrouter_client.py` to use the correct names, it will still work

## Files Modified

- [`src/utils/langfuse_tracer.py`](src/utils/langfuse_tracer.py) - Updated `update_current_observation()` function to transform usage field names

## Testing

### Unit Test

Run the test suite to verify the transformation:

```bash
cd gedcom-generation-microservice
. ~/venv/bin/activate
python test_cost_tracking_fix.py
```

Expected output:
```
✓ All tests passed!
```

### Integration Test

To verify costs appear in Langfuse:

1. **Ensure Langfuse is configured:**
   ```bash
   # Check environment variables
   python check_env.py
   ```

2. **Process a document through the pipeline:**
   - Upload an image to trigger the full pipeline
   - Wait for GEDCOM generation to complete

3. **Check Langfuse dashboard:**
   - Navigate to https://cloud.langfuse.com (or your Langfuse instance)
   - Go to "Generations" view
   - Look for recent traces with model name `google/gemini-flash-1.5`
   - Verify you see:
     - ✓ Token usage (prompt_tokens, completion_tokens)
     - ✓ Cost calculations
     - ✓ Model name displayed correctly

## What Gets Tracked Now

With this fix, Langfuse now properly tracks:

1. **Token Usage**
   - `prompt_tokens` - Input tokens sent to the model
   - `completion_tokens` - Output tokens generated by the model
   - `total_tokens` - Total tokens used

2. **Cost Calculation**
   - Langfuse automatically calculates costs based on:
     - Model name (e.g., `google/gemini-flash-1.5`)
     - Token usage
     - Model pricing in Langfuse's database

3. **Dashboard Metrics**
   - Cost per generation
   - Total cost per session/trace
   - Cost trends over time
   - Cost breakdown by model

## Verification Checklist

After deploying this fix, verify:

- [ ] Traces appear in Langfuse dashboard
- [ ] Model name is displayed (e.g., `google/gemini-flash-1.5`)
- [ ] Token usage shows `prompt_tokens` and `completion_tokens`
- [ ] Cost is calculated and displayed
- [ ] Cost appears in the dashboard summary

## Related Documentation

- [LANGFUSE_MODEL_NAME_FIX.md](LANGFUSE_MODEL_NAME_FIX.md) - Previous fix for model name tracking
- [LANGFUSE_TRACING.md](LANGFUSE_TRACING.md) - General Langfuse tracing documentation
- [LANGFUSE_V4_COMPATIBILITY_FIX.md](LANGFUSE_V4_COMPATIBILITY_FIX.md) - Langfuse v4.x compatibility
- [Langfuse Model Usage & Cost Tracking](https://langfuse.com/docs/model-usage-and-cost) - Official documentation

## Technical Details

### Why Langfuse Uses OpenAI Field Names

Langfuse follows the OpenAI API standard for usage data:
- `prompt_tokens` - Standard name in OpenAI API
- `completion_tokens` - Standard name in OpenAI API
- `total_tokens` - Standard name in OpenAI API

This allows Langfuse to:
- Work seamlessly with OpenAI SDK
- Support multiple LLM providers that follow OpenAI standards
- Maintain consistent cost calculation across providers

### Why We Used Generic Names

The code originally used generic names (`input`, `output`, `total`) to be provider-agnostic. However, this prevented Langfuse from recognizing the data.

The fix maintains this abstraction in the application code while transforming to the standard format when sending to Langfuse.

## Future Improvements

Consider updating `openrouter_client.py` to use the standard field names directly:

```python
# Instead of:
usage={
    "input": response.usage.prompt_tokens,
    "output": response.usage.completion_tokens,
    "total": response.usage.total_tokens
}

# Use:
usage={
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens,
    "total_tokens": response.usage.total_tokens
}
```

This would:
- Remove the need for transformation
- Make the code more standard
- Improve clarity

However, the current fix works without requiring changes to multiple files.
