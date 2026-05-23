"""
Langfuse configuration and initialization for Flask application.

This module sets up Langfuse tracing for the genealogy application,
following best practices from the Langfuse skill.
"""

import os
import logging
from functools import wraps
from flask import request, g, has_request_context
from langfuse import get_client, propagate_attributes

logger = logging.getLogger(__name__)


def init_langfuse(app):
    """
    Initialize Langfuse for the Flask application.
    
    This function should be called after environment variables are loaded
    but before the application starts handling requests.
    
    Args:
        app: Flask application instance
    """
    # Check if Langfuse credentials are configured
    langfuse_secret = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_public = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_host = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
    
    if not langfuse_secret or not langfuse_public:
        logger.warning(
            "Langfuse credentials not configured. Tracing will be disabled. "
            "Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY environment variables to enable tracing."
        )
        app.config['LANGFUSE_ENABLED'] = False
        return
    
    try:
        # Initialize Langfuse client (singleton pattern)
        langfuse = get_client()
        app.config['LANGFUSE_ENABLED'] = True
        logger.info(f"Langfuse initialized successfully. Host: {langfuse_host}")
        
        # Register shutdown handler to flush traces
        @app.teardown_appcontext
        def shutdown_langfuse(exception=None):
            """Flush Langfuse traces on application shutdown."""
            try:
                langfuse.flush()
            except Exception as e:
                logger.error(f"Error flushing Langfuse traces: {e}")
        
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        app.config['LANGFUSE_ENABLED'] = False


def trace_request(trace_name=None, capture_input=True, capture_output=True):
    """
    Decorator to trace Flask route handlers with Langfuse.
    
    This decorator creates a trace for each request, capturing:
    - Request method and path
    - Request parameters
    - Response status and data
    - User session information
    - Execution time
    
    Args:
        trace_name: Optional custom name for the trace. If None, uses route endpoint name.
        capture_input: Whether to capture request data as trace input (default: True)
        capture_output: Whether to capture response data as trace output (default: True)
    
    Example:
        @bp.route("/persons")
        @trace_request(trace_name="list-persons")
        def list_persons():
            # Your route logic here
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip tracing if Langfuse is not enabled
            from flask import current_app
            if not current_app.config.get('LANGFUSE_ENABLED', False):
                return f(*args, **kwargs)
            
            langfuse = get_client()
            
            # Determine trace name
            name = trace_name or f.__name__
            
            # Prepare trace input
            trace_input = None
            if capture_input and has_request_context():
                trace_input = {
                    "method": request.method,
                    "path": request.path,
                    "endpoint": request.endpoint,
                }
                
                # Add query parameters if present
                if request.args:
                    trace_input["query_params"] = dict(request.args)
                
                # Add form data for POST requests (excluding file uploads)
                if request.method in ['POST', 'PUT', 'PATCH'] and request.form:
                    trace_input["form_data"] = {
                        k: v for k, v in request.form.items() 
                        if k not in ['password', 'secret', 'token']  # Exclude sensitive fields
                    }
            
            # Create trace with context manager
            with langfuse.start_as_current_observation(
                as_type="span",
                name=name,
                input=trace_input
            ) as span:
                # Set trace attributes
                with propagate_attributes(
                    session_id=request.cookies.get('session') if has_request_context() else None,
                    metadata={
                        "route": request.endpoint if has_request_context() else None,
                        "method": request.method if has_request_context() else None,
                    },
                    tags=["flask", "genealogy-app"]
                ):
                    try:
                        # Execute the route handler
                        response = f(*args, **kwargs)
                        
                        # Capture output if enabled
                        if capture_output:
                            # For JSON responses, capture the data
                            if hasattr(response, 'get_json'):
                                try:
                                    json_data = response.get_json()
                                    if json_data:
                                        # Limit output size to avoid large traces
                                        if isinstance(json_data, dict):
                                            output_data = {
                                                "status": "success",
                                                "data_keys": list(json_data.keys()) if isinstance(json_data, dict) else None
                                            }
                                        else:
                                            output_data = {"status": "success"}
                                        span.update(output=output_data)
                                except Exception:
                                    pass
                            else:
                                span.update(output={"status": "success"})
                        
                        return response
                        
                    except Exception as e:
                        # Log error in trace
                        span.update(
                            output={
                                "status": "error",
                                "error": str(e),
                                "error_type": type(e).__name__
                            },
                            level="ERROR"
                        )
                        raise
        
        return decorated_function
    return decorator


def trace_function(name=None, capture_input=True, capture_output=True):
    """
    Decorator to trace individual functions with Langfuse.
    
    This is useful for tracing service functions, parsers, or other
    non-route functions that you want to observe.
    
    Args:
        name: Optional custom name for the span. If None, uses function name.
        capture_input: Whether to capture function arguments (default: True)
        capture_output: Whether to capture function return value (default: True)
    
    Example:
        @trace_function(name="parse-gedcom")
        def parse_gedcom_file(filepath):
            # Your parsing logic here
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip tracing if Langfuse is not enabled
            from flask import current_app
            if not current_app.config.get('LANGFUSE_ENABLED', False):
                return f(*args, **kwargs)
            
            langfuse = get_client()
            
            # Determine span name
            span_name = name or f.__name__
            
            # Prepare input (avoid capturing sensitive data)
            span_input = None
            if capture_input:
                # Only capture non-sensitive arguments
                span_input = {
                    "function": f.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()) if kwargs else []
                }
            
            # Create span with context manager
            with langfuse.start_as_current_observation(
                as_type="span",
                name=span_name,
                input=span_input
            ) as span:
                try:
                    # Execute the function
                    result = f(*args, **kwargs)
                    
                    # Capture output if enabled
                    if capture_output and result is not None:
                        # Limit output size
                        if isinstance(result, dict):
                            output_data = {
                                "status": "success",
                                "result_keys": list(result.keys())
                            }
                        elif isinstance(result, (list, tuple)):
                            output_data = {
                                "status": "success",
                                "result_count": len(result)
                            }
                        else:
                            output_data = {"status": "success"}
                        
                        span.update(output=output_data)
                    
                    return result
                    
                except Exception as e:
                    # Log error in span
                    span.update(
                        output={
                            "status": "error",
                            "error": str(e),
                            "error_type": type(e).__name__
                        },
                        level="ERROR"
                    )
                    raise
        
        return decorated_function
    return decorator
