# Langfuse Integration Guide

This document explains how Langfuse tracing has been integrated into the genealogy application following best practices from the [Langfuse AI skill](https://github.com/langfuse/skills).

## Overview

Langfuse is an open-source LLM engineering platform that provides observability and tracing for AI applications. This integration adds comprehensive tracing to the Flask genealogy application, allowing you to:

- Monitor request performance and execution times
- Debug issues by viewing detailed trace hierarchies
- Track user sessions and behavior patterns
- Analyze API usage and identify bottlenecks
- Filter and search traces by tags, users, and sessions

## Installation

### 1. Install Dependencies

The Langfuse Python SDK has been added to [`requirements.txt`](requirements.txt):

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Add your Langfuse credentials to your `.env` file (see [`.env.example`](.env.example) for reference):

```bash
# Langfuse Configuration
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com  # EU region
```

**Getting Credentials:**
- Sign up for a free account at [Langfuse Cloud](https://cloud.langfuse.com)
- Or [self-host Langfuse](https://langfuse.com/docs/deployment/self-host)
- Find your API keys in: Settings → API Keys

**Data Regions:**
- 🇪🇺 EU: `https://cloud.langfuse.com`
- 🇺🇸 US: `https://us.cloud.langfuse.com`
- 🇯🇵 Japan: `https://jp.cloud.langfuse.com`
- ⚕️ HIPAA: `https://hipaa.cloud.langfuse.com`

### 3. Start the Application

The integration is automatically initialized when the Flask app starts:

```bash
python src/main.py
```

If Langfuse credentials are not configured, the application will log a warning and continue running without tracing.

## Architecture

### Core Components

1. **[`src/app/langfuse_config.py`](src/app/langfuse_config.py)** - Langfuse configuration module
   - `init_langfuse(app)` - Initializes Langfuse client and registers shutdown handlers
   - `@trace_request()` - Decorator for tracing Flask route handlers
   - `@trace_function()` - Decorator for tracing individual functions

2. **[`src/app/__init__.py`](src/app/__init__.py)** - Flask app initialization
   - Calls `init_langfuse(app)` after loading configuration
   - Registers teardown handler to flush traces on shutdown

3. **[`src/app/routes/main.py`](src/app/routes/main.py)** - Route handlers with tracing
   - Key routes decorated with `@trace_request()`
   - Captures request/response data and execution context

### Integration Pattern

The integration follows the **decorator pattern** recommended by the Langfuse skill:

```python
from langfuse_config import trace_request

@bp.route("/persons")
@trace_request(trace_name="list-persons", capture_output=False)
def list_persons():
    # Your route logic here
    pass
```

## Features

### 1. Automatic Request Tracing

All decorated routes automatically capture:
- **Request metadata**: HTTP method, path, endpoint, query parameters
- **Session information**: Session ID from cookies
- **Response status**: Success/error status
- **Execution time**: Automatic latency tracking
- **Error details**: Exception type and message on failures

### 2. Trace Attributes

Each trace includes:
- **Tags**: `["flask", "genealogy-app"]` for filtering
- **Session ID**: Extracted from request cookies
- **Metadata**: Route name, HTTP method
- **Input/Output**: Request parameters and response summaries

### 3. Sensitive Data Protection

The integration automatically excludes sensitive fields:
- Password fields
- Secret tokens
- API keys
- Large response bodies (summarized instead)

### 4. Graceful Degradation

If Langfuse is not configured or fails to initialize:
- Application continues running normally
- Warning logged to console
- No tracing overhead added

## Traced Routes

The following routes have been instrumented with Langfuse tracing:

### Core Routes
- `GET /` - Index page (list uploaded files)
- `POST /upload` - Upload GEDCOM file
- `POST /parse/<file_id>` - Parse GEDCOM file

### Person Management
- `GET /persons` - List persons page
- `GET /api/persons` - List persons API
- `GET /api/persons/<person_id>/details` - Get person details

### Graph Visualization
- `GET /graph` - Graph visualizer page
- `GET /api/graph/data` - Get graph data

### Duplicate Detection
- `GET /duplicates` - Duplicates review page
- `POST /api/duplicates/<candidate_id>/review` - Review duplicate

## Usage Examples

### Basic Route Tracing

```python
from langfuse_config import trace_request

@bp.route("/my-route")
@trace_request(trace_name="my-custom-trace")
def my_route():
    # Your logic here
    return jsonify({"status": "success"})
```

### Function Tracing

For non-route functions (services, parsers, etc.):

```python
from langfuse_config import trace_function

@trace_function(name="parse-gedcom-file")
def parse_gedcom_file(filepath):
    # Your parsing logic
    return parsed_data
```

### Nested Tracing

Create nested spans for complex operations:

```python
from langfuse import get_client

langfuse = get_client()

@bp.route("/complex-operation")
@trace_request(trace_name="complex-operation")
def complex_operation():
    # Parent span created by decorator
    
    # Create nested span for sub-operation
    with langfuse.start_as_current_observation(
        as_type="span",
        name="sub-operation"
    ) as span:
        result = perform_sub_operation()
        span.update(output={"result": result})
    
    return jsonify({"status": "success"})
```

### Adding Custom Metadata

```python
from langfuse import get_client, propagate_attributes

langfuse = get_client()

@bp.route("/custom-metadata")
@trace_request(trace_name="custom-metadata")
def custom_metadata():
    # Add custom attributes to all child observations
    with propagate_attributes(
        user_id="user_123",
        session_id="session_abc",
        tags=["custom-tag"],
        metadata={"experiment": "variant_a"}
    ):
        # Your logic here
        pass
    
    return jsonify({"status": "success"})
```

## Viewing Traces

### Access the Langfuse Dashboard

1. Navigate to your Langfuse instance (e.g., https://cloud.langfuse.com)
2. Select your project
3. Go to the **Traces** view

### Trace Details

Each trace shows:
- **Timeline**: Visual representation of span hierarchy
- **Input/Output**: Request and response data
- **Metadata**: Tags, session ID, user ID
- **Performance**: Latency for each span
- **Errors**: Stack traces and error messages

### Filtering Traces

Use filters to find specific traces:
- **Tags**: Filter by `flask`, `genealogy-app`, or custom tags
- **Session ID**: View all requests from a user session
- **Status**: Filter by success/error status
- **Time range**: View traces from specific time periods

## Best Practices

### 1. Trace Naming

Use descriptive, kebab-case names:
```python
@trace_request(trace_name="upload-gedcom-file")  # Good
@trace_request(trace_name="upload")              # Less descriptive
```

### 2. Capture Control

Disable output capture for HTML pages to reduce trace size:
```python
@trace_request(trace_name="index-page", capture_output=False)
def index():
    return render_template("index.html")
```

### 3. Sensitive Data

Never log sensitive information:
```python
# The decorator automatically excludes these fields
sensitive_fields = ['password', 'secret', 'token', 'api_key']
```

### 4. Error Handling

Errors are automatically captured in traces:
```python
@trace_request(trace_name="my-route")
def my_route():
    try:
        # Your logic
        pass
    except Exception as e:
        # Error automatically logged to trace
        raise
```

### 5. Performance

Langfuse uses async requests, adding minimal latency:
- Traces are queued and sent in background
- No blocking on trace submission
- Automatic batching for efficiency

## Troubleshooting

### Traces Not Appearing

1. **Check credentials**: Verify `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` are set
2. **Check logs**: Look for Langfuse initialization messages
3. **Flush traces**: In short-lived scripts, call `langfuse.flush()`
4. **Network**: Ensure your server can reach the Langfuse host

### Application Errors

If Langfuse causes issues:
1. **Disable tracing**: Remove or comment out Langfuse environment variables
2. **Check logs**: Look for Langfuse-related error messages
3. **Update SDK**: Ensure you're using the latest version

### Performance Issues

If tracing adds latency:
1. **Reduce capture**: Set `capture_output=False` for large responses
2. **Limit traced routes**: Only trace critical endpoints
3. **Check network**: Slow network to Langfuse host can cause delays

## Advanced Features

### Session Tracking

Track user sessions across requests:
```python
from flask import session

# Session ID automatically extracted from cookies
# Or set explicitly:
with propagate_attributes(session_id="custom-session-id"):
    # Your logic
    pass
```

### User Identification

Associate traces with users:
```python
with propagate_attributes(user_id="user_123"):
    # Your logic
    pass
```

### Custom Tags

Add tags for filtering:
```python
with propagate_attributes(tags=["experiment-a", "production"]):
    # Your logic
    pass
```

### Scoring Traces

Add quality scores to traces:
```python
from langfuse import get_client

langfuse = get_client()

# Score a trace
langfuse.score_current_trace(
    name="user-feedback",
    value=1,
    data_type="NUMERIC",
    comment="User rated this response positively"
)
```

## Resources

- [Langfuse Documentation](https://langfuse.com/docs)
- [Langfuse Python SDK](https://python.reference.langfuse.com)
- [Langfuse Skill Repository](https://github.com/langfuse/skills)
- [Flask Integration Guide](https://langfuse.com/docs/integrations/frameworks/flask)

## Support

For issues or questions:
- [Langfuse Discord](https://discord.gg/langfuse)
- [GitHub Issues](https://github.com/langfuse/langfuse/issues)
- [Documentation](https://langfuse.com/docs)
