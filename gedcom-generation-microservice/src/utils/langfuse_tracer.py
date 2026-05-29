"""Simplified Langfuse wrapper for v4.x API."""
import logging
import traceback
from typing import Optional, Any, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)

try:
    from langfuse import observe, Langfuse
    _langfuse_available = True
    _langfuse_client = None
    logger.info("Langfuse v4.x successfully imported")
except ImportError as e:
    logger.warning(f"Langfuse not available: {e}")
    _langfuse_available = False
    
    # Provide no-op decorator if Langfuse not installed
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])
    
    class Langfuse:
        def flush(self):
            pass
        
        def get_trace_url(self):
            return None
        
        def score_current_trace(self, *args, **kwargs):
            pass
    

# Re-export for convenience
__all__ = [
    'observe',
    'Langfuse',
    'is_available',
    'get_client',
    'flush',
    'add_score',
    'create_span',
    'log_error',
    'update_current_observation',
    'update_current_trace'
]

def is_available() -> bool:
    """Check if Langfuse is available."""
    return _langfuse_available

def get_client() -> Optional[Langfuse]:
    """Get Langfuse client for advanced operations."""
    global _langfuse_client
    if _langfuse_available:
        if _langfuse_client is None:
            _langfuse_client = Langfuse()
        return _langfuse_client
    return None

def flush():
    """Flush any pending traces."""
    if _langfuse_available:
        try:
            client = get_client()
            if client:
                client.flush()
                logger.info("Langfuse traces flushed")
        except Exception as e:
            logger.error(f"Error flushing Langfuse traces: {e}")

def update_current_observation(**kwargs) -> None:
    """
    Update the current observation with additional metadata.
    
    In Langfuse v4.x, this uses the client's update_current_span() or
    update_current_generation() methods depending on the observation type.
    
    Args:
        **kwargs: Keyword arguments to pass to update methods
                  Common args: model, input, output, usage, metadata, model_parameters
    
    Example:
        update_current_observation(
            model="google/gemini-flash-1.5",
            model_parameters={"temperature": 0.0},
            usage={"input": 100, "output": 50, "total": 150}
        )
    """
    if _langfuse_available:
        try:
            client = get_client()
            if client:
                # Separate parameters for generation vs span
                # update_current_generation accepts: name, input, output, metadata, version,
                # level, status_message, completion_start_time, model, model_parameters,
                # usage_details, cost_details, prompt
                generation_params = {}
                span_params = {}
                
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
                
                # Common parameters for both
                for key in ['name', 'input', 'output', 'metadata', 'version', 'level', 'status_message']:
                    if key in kwargs:
                        generation_params[key] = kwargs[key]
                        span_params[key] = kwargs[key]
                
                # Generation-specific parameters
                for key in ['model', 'model_parameters', 'completion_start_time', 'cost_details', 'prompt']:
                    if key in kwargs:
                        generation_params[key] = kwargs[key]
                
                # Try updating as generation first (most common for LLM calls)
                try:
                    if generation_params:
                        client.update_current_generation(**generation_params)
                        logger.debug(f"Updated current generation with: {list(generation_params.keys())}")
                except Exception as gen_error:
                    # Fall back to updating as span (only with span-compatible params)
                    try:
                        if span_params:
                            client.update_current_span(**span_params)
                            logger.debug(f"Updated current span with: {list(span_params.keys())}")
                    except Exception as span_error:
                        logger.debug(f"Could not update as generation or span: {gen_error}, {span_error}")
        except Exception as e:
            logger.error(f"Error updating current observation: {e}")

def update_current_trace(**kwargs) -> None:
    """
    Update the current trace with additional metadata.
    
    In Langfuse v4.x, trace updates are handled through the client instance.
    Note: Direct trace updates may have limited support in v4.x; use observation
    updates or trace-level methods like set_current_trace_io() instead.
    
    Args:
        **kwargs: Keyword arguments for trace metadata
                  Common args: session_id, tags, metadata, user_id
    
    Example:
        update_current_trace(
            session_id="document-123",
            tags=["document-processing"],
            metadata={"document_type": "baptism"}
        )
    """
    if _langfuse_available:
        try:
            client = get_client()
            if client:
                # In v4.x, trace updates are more limited
                # Log the metadata for now; actual trace updates happen via observations
                logger.debug(f"Trace metadata (v4.x): {list(kwargs.keys())}")
                # Note: v4.x doesn't have a direct update_current_trace method
                # Trace metadata should be set via @observe decorator or observation updates
        except Exception as e:
            logger.error(f"Error updating current trace: {e}")

def add_score(name: str, value: float, comment: Optional[str] = None) -> None:
    """
    Add a score to the current trace.
    
    Args:
        name: Name of the score metric
        value: Numeric value of the score
        comment: Optional comment describing the score
    """
    if _langfuse_available:
        try:
            client = get_client()
            if client:
                client.score_current_trace(
                    name=name,
                    value=value,
                    comment=comment
                )
                logger.debug(f"Added score: {name}={value}")
        except Exception as e:
            logger.error(f"Error adding score {name}: {e}")

@contextmanager
def create_span(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Create a Langfuse span as a context manager.
    
    Note: In Langfuse v4.x, spans are automatically managed by the @observe decorator.
    This function is kept for backward compatibility but is now a no-op.
    Use @observe decorator on functions instead for proper span tracking.
    
    Args:
        name: Name of the span (logged but not used in v4.x)
        metadata: Optional metadata (logged but not used in v4.x)
    
    Yields:
        None (v4.x uses @observe decorator for span management)
    
    Example:
        with create_span("process-document-group", metadata={"document_id": doc_id}):
            # Your processing code here
            pass
    """
    if _langfuse_available:
        logger.debug(f"Span context: {name} (v4.x uses @observe decorator)")
        if metadata:
            logger.debug(f"Span metadata: {metadata}")
    yield None

def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "ERROR"
) -> None:
    """
    Log an error with context information.
    
    Note: In Langfuse v4.x, errors are automatically captured by the @observe decorator
    when exceptions are raised within observed functions. This function now logs to
    standard logging for backward compatibility.
    
    Args:
        error: The exception that occurred
        context: Optional dictionary with additional context (e.g., document_id, operation)
        level: Error level (ERROR, WARNING, etc.)
    
    Example:
        try:
            # Some operation
            pass
        except Exception as e:
            log_error(e, context={"document_id": doc_id, "operation": "gedcom_generation"})
            raise
    """
    # Build error metadata
    error_metadata = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "stack_trace": traceback.format_exc(),
        "level": level
    }
    
    # Add additional context if provided
    if context:
        error_metadata.update(context)
    
    # Log to standard logging (Langfuse v4.x captures errors automatically via @observe)
    logger.error(
        f"{level}: {type(error).__name__}: {str(error)}",
        extra={"langfuse_metadata": error_metadata}
    )
