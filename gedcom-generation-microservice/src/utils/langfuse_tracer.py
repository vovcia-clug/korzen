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
    'log_error'
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
