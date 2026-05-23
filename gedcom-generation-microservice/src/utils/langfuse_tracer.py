"""Simplified Langfuse wrapper for v4.x API."""
import logging
from typing import Optional

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
__all__ = ['observe', 'Langfuse', 'is_available', 'get_client', 'flush', 'add_score']

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
