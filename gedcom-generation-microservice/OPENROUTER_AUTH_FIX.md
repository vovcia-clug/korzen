# OpenRouter Authorization Fix Documentation

## Problem Description

The GEDCOM Generation Microservice was experiencing **401 Unauthorized errors** when making API calls to OpenRouter, despite having a valid API key configured. The service would fail to generate GEDCOM files, causing the entire OCR-to-GEDCOM pipeline to stall.

### Symptoms
- Consistent 401 Unauthorized responses from OpenRouter API
- Error messages indicating authentication failure
- Valid API key confirmed working in other tools (curl, Postman)
- Service unable to complete GEDCOM generation requests

### Impact
- Complete service failure - no GEDCOM files could be generated
- Pipeline blockage - OCR results accumulated in SQS queue without processing
- Manual intervention required to diagnose and resolve the issue

## Root Cause

The issue was caused by **duplicate Authorization headers** being sent in API requests to OpenRouter.

### Technical Explanation

The service uses the OpenAI Python SDK to communicate with OpenRouter's OpenAI-compatible API endpoint. When initializing the SDK client:

```python
self.client = AsyncOpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=timeout
)
```

**The OpenAI SDK automatically adds an `Authorization: Bearer <api_key>` header to all requests.** This is standard behavior for the SDK and is the correct way to authenticate.

However, the code was **manually adding a redundant Authorization header** in the `generate_gedcom()` method:

```python
# PROBLEMATIC CODE (before fix)
response = await self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    temperature=0.0,
    extra_headers={
        "Authorization": f"Bearer {self.api_key}",  # ❌ REDUNDANT!
        "HTTP-Referer": "https://github.com/korzen",
        "X-Title": "GEDCOM Generation Service"
    }
)
```

### Why This Caused 401 Errors

When both the SDK and the application code add Authorization headers:

1. **Header Conflict**: HTTP allows multiple headers with the same name, but the behavior is undefined for Authorization headers
2. **OpenRouter Rejection**: OpenRouter's API server likely saw conflicting Authorization headers and rejected the request
3. **Unpredictable Behavior**: Depending on header processing order, the wrong header value might be used, or the request might be rejected entirely

This is a common pitfall when using SDK clients that handle authentication automatically - developers may not realize the SDK is already managing authentication and attempt to add it manually.

## Solution Implemented

The fix involved removing the redundant manual authorization handling and relying entirely on the OpenAI SDK's built-in authentication mechanism.

### Changes Made

**File**: [`gedcom-generation-microservice/src/services/openrouter_client.py`](gedcom-generation-microservice/src/services/openrouter_client.py)

#### Change 1: Removed Redundant Authorization Header

**Before** (lines 129-134):
```python
extra_headers={
    "Authorization": f"Bearer {self.api_key}",  # ❌ Removed
    "HTTP-Referer": "https://github.com/korzen",
    "X-Title": "GEDCOM Generation Service"
}
```

**After** (lines 129-133):
```python
extra_headers={
    # Authorization header is automatically added by OpenAI SDK
    "HTTP-Referer": "https://github.com/korzen",
    "X-Title": "GEDCOM Generation Service"
}
```

#### Change 2: Removed Unnecessary API Key Storage

**Before** (in `__init__` method):
```python
self.api_key = api_key  # ❌ Removed - not needed
```

**After**:
```python
# Removed - SDK stores API key internally
```

The API key is passed to the SDK during initialization and stored internally by the SDK. There's no need to store it again in the class instance.

#### Change 3: Added Clarifying Comment

**Added** (line 74):
```python
# SDK automatically adds Authorization header to all requests
```

This comment serves as documentation to prevent future developers from reintroducing the same bug.

### Code Diff Summary

```diff
  def __init__(self, ...):
      if not api_key:
          raise ValueError("OPENROUTER_API_KEY is required")
      
      self.client = AsyncOpenAI(
          api_key=api_key,
          base_url=base_url,
          timeout=timeout
      )
      
-     self.api_key = api_key
+     # SDK automatically adds Authorization header to all requests
      
      self.model = model
      ...

  async def generate_gedcom(self, ...):
      response = await self.client.chat.completions.create(
          model=self.model,
          messages=messages,
          temperature=0.0,
          extra_headers={
-             "Authorization": f"Bearer {self.api_key}",
+             # Authorization header is automatically added by OpenAI SDK
              "HTTP-Referer": "https://github.com/korzen",
              "X-Title": "GEDCOM Generation Service"
          }
      )
```

## Testing Instructions

Follow these steps to verify the fix works correctly:

### 1. Verify API Key Configuration

Check that the OpenRouter API key is properly configured:

```bash
cd gedcom-generation-microservice
python check_env.py
```

Expected output should show:
```
✓ OPENROUTER_API_KEY is set (length: 64)
```

### 2. Check Environment Variables

Ensure your `.env` file contains:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-flash-1.5
```

### 3. Run the Service

Start the GEDCOM generation service:

```bash
cd gedcom-generation-microservice
python -m src.main
```

### 4. Monitor Logs for Success Indicators

Watch for these log messages indicating successful authentication:

**Initialization Success**:
```
INFO - API key loaded: sk-or-v1-... (length: 64)
INFO - Initialized OpenRouter client with model: google/gemini-flash-1.5, base_url: https://openrouter.ai/api/v1
```

**Successful API Call**:
```
INFO - Generating GEDCOM from 15234 characters of formatted text
DEBUG - Attempt 1/3 to call OpenRouter API
DEBUG - Received response: 8456 characters
INFO - Successfully generated GEDCOM (8456 bytes) (usage: 12500 tokens)
```

### 5. Verify GEDCOM Generation Completes

Check that the service:

1. **Receives OCR results** from SQS queue
2. **Groups documents** by document_id
3. **Calls OpenRouter API** without 401 errors
4. **Generates valid GEDCOM** files
5. **Uploads to S3** successfully
6. **Publishes completion message** to GEDCOM ready queue

### 6. Check for Authentication Errors

**Before the fix**, you would see:
```
ERROR - API error on attempt 1/3: 401 Unauthorized
ERROR - API error on attempt 2/3: 401 Unauthorized
ERROR - API error on attempt 3/3: 401 Unauthorized
ERROR - Failed to generate GEDCOM after all retries
```

**After the fix**, these errors should NOT appear. If you still see 401 errors, verify:
- API key is valid and not expired
- API key has sufficient credits on OpenRouter
- Network connectivity to OpenRouter API

### 7. Test with Sample Document

To test end-to-end, send a test OCR result message to the input queue and verify:

```bash
# The service should process it without authentication errors
# Check CloudWatch logs or local logs for success messages
```

## Technical Details

### How the OpenAI SDK Handles Authentication

The OpenAI Python SDK (which OpenRouter uses for compatibility) handles authentication through its initialization:

```python
client = AsyncOpenAI(
    api_key="your-api-key",
    base_url="https://openrouter.ai/api/v1"
)
```

Internally, the SDK:

1. **Stores the API key** in the client instance
2. **Automatically adds** `Authorization: Bearer <api_key>` header to every request
3. **Manages header injection** at the HTTP client level (using `httpx`)
4. **Ensures consistency** across all API calls

### Why extra_headers Exists

The `extra_headers` parameter in SDK methods is designed for:

- **Custom application headers** (like `HTTP-Referer`, `X-Title`)
- **OpenRouter-specific headers** (like `X-Title` for app identification)
- **Debugging headers** (like request IDs)

It is **NOT** intended for authentication headers, as those are managed by the SDK automatically.

### OpenRouter API Compatibility

OpenRouter provides an OpenAI-compatible API endpoint, which means:

- Uses the same request/response format as OpenAI
- Accepts the same authentication mechanism (Bearer token)
- Works with the official OpenAI SDK
- Requires only changing the `base_url` parameter

This compatibility is why we can use `AsyncOpenAI` from the `openai` package to communicate with OpenRouter.

## Prevention Guidelines

To prevent this issue from being reintroduced in the future:

### 1. Trust SDK Authentication

**DO NOT** manually add Authorization headers when using SDK clients that handle authentication:

```python
# ❌ WRONG - Don't do this
extra_headers={
    "Authorization": f"Bearer {api_key}"
}

# ✅ CORRECT - Let the SDK handle it
extra_headers={
    "HTTP-Referer": "https://github.com/korzen",
    "X-Title": "GEDCOM Generation Service"
}
```

### 2. Read SDK Documentation

Before adding authentication headers, check the SDK documentation:
- [OpenAI Python SDK Documentation](https://github.com/openai/openai-python)
- [OpenRouter API Documentation](https://openrouter.ai/docs)

Most modern SDK clients handle authentication automatically when you provide credentials during initialization.

### 3. Code Review Checklist

When reviewing code that uses API clients, check for:

- [ ] API key passed to SDK during initialization
- [ ] No manual Authorization headers in request calls
- [ ] No redundant credential storage in class instances
- [ ] Proper use of `extra_headers` for custom headers only

### 4. Testing Best Practices

When testing API integrations:

1. **Test with real API calls** - Don't rely solely on mocks
2. **Check HTTP request logs** - Verify headers being sent
3. **Test authentication failures** - Ensure proper error handling
4. **Monitor for 401 errors** - Set up alerts for authentication issues

### 5. Documentation

When implementing SDK-based API clients:

- Document that authentication is handled by the SDK
- Add comments explaining why manual auth headers are not needed
- Include examples of correct `extra_headers` usage
- Reference this document for future developers

### 6. Common Pitfalls to Avoid

**Pitfall 1: Assuming Manual Auth is Needed**
```python
# ❌ Don't assume you need to add auth manually
# The SDK already does this!
```

**Pitfall 2: Copying Code from HTTP Client Examples**
```python
# ❌ Don't copy raw HTTP client code that includes auth headers
# SDK clients abstract this away
```

**Pitfall 3: Storing API Keys Unnecessarily**
```python
# ❌ Don't store API keys in instance variables
self.api_key = api_key  # Not needed - SDK stores it

# ✅ Just pass to SDK during init
self.client = AsyncOpenAI(api_key=api_key)
```

## Related Documentation

- [`README.md`](README.md) - Service overview and configuration
- [OpenRouter API Documentation](https://openrouter.ai/docs)
- [OpenAI Python SDK](https://github.com/openai/openai-python)

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-05-23 | 1.0.0 | Initial documentation of authorization fix |

---

**Last Updated**: 2026-05-23  
**Maintainer**: GEDCOM Generation Microservice Team
