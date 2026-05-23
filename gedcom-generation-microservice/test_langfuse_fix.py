#!/usr/bin/env python3
"""
Test script to validate Langfuse API fix.

This script tests that the Langfuse tracing utilities work correctly
with the StaticTraceClient API.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.logger import setup_logger
from config import Config

# Setup logger
logger = setup_logger(__name__, level="DEBUG")

def test_langfuse_initialization():
    """Test that Langfuse initializes without errors."""
    from utils import langfuse_tracer
    
    logger.info("Testing Langfuse initialization...")
    
    # Initialize Langfuse
    langfuse_tracer.initialize_langfuse()
    
    if langfuse_tracer.is_enabled():
        logger.info("✓ Langfuse is enabled")
        client = langfuse_tracer.get_client()
        logger.info(f"✓ Langfuse client: {type(client).__name__}")
    else:
        logger.info("✓ Langfuse is disabled (not configured or import failed)")
    
    return True


def test_trace_creation():
    """Test that traces can be created without AttributeError."""
    from utils import langfuse_tracer
    
    logger.info("\nTesting trace creation...")
    
    try:
        with langfuse_tracer.trace_context(
            name="test-trace",
            input_data={"test": "data"},
            metadata={"test_run": True},
            tags=["test"]
        ) as trace:
            if trace:
                logger.info(f"✓ Trace created successfully: {type(trace).__name__}")
                logger.info(f"✓ Trace ID: {trace.trace_id}")
                
                # Test updating trace
                trace.update(output={"status": "success"})
                logger.info("✓ Trace updated successfully")
            else:
                logger.info("✓ Trace is None (Langfuse disabled, expected behavior)")
        
        logger.info("✓ Trace context manager completed without errors")
        return True
        
    except AttributeError as e:
        logger.error(f"✗ AttributeError (API issue): {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_span_creation():
    """Test that spans can be created within traces."""
    from utils import langfuse_tracer
    
    logger.info("\nTesting span creation...")
    
    try:
        with langfuse_tracer.trace_context(
            name="test-trace-with-span",
            input_data={"test": "data"}
        ) as trace:
            if trace:
                with langfuse_tracer.span_context(
                    trace,
                    "test-span",
                    input_data={"span_test": "data"}
                ) as span:
                    if span:
                        logger.info(f"✓ Span created successfully: {type(span).__name__}")
                        span.update(output={"status": "success"})
                        logger.info("✓ Span updated successfully")
                    else:
                        logger.info("✓ Span is None (expected when Langfuse disabled)")
            else:
                logger.info("✓ Trace is None (Langfuse disabled)")
        
        logger.info("✓ Span context manager completed without errors")
        return True
        
    except AttributeError as e:
        logger.error(f"✗ AttributeError (API issue): {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generation_creation():
    """Test that generation contexts can be created."""
    from utils import langfuse_tracer
    
    logger.info("\nTesting generation creation...")
    
    try:
        with langfuse_tracer.trace_context(
            name="test-trace-with-generation",
            input_data={"test": "data"}
        ) as trace:
            if trace:
                with langfuse_tracer.generation_context(
                    trace,
                    "test-generation",
                    model="test-model",
                    input_data={"prompt": "test"},
                    model_parameters={"temperature": 0.0}
                ) as generation:
                    if generation:
                        logger.info(f"✓ Generation created successfully: {type(generation).__name__}")
                        generation.update(
                            output={"content": "test response"},
                            usage={"input_tokens": 10, "output_tokens": 20}
                        )
                        logger.info("✓ Generation updated successfully")
                    else:
                        logger.info("✓ Generation is None (expected when Langfuse disabled)")
            else:
                logger.info("✓ Trace is None (Langfuse disabled)")
        
        logger.info("✓ Generation context manager completed without errors")
        return True
        
    except AttributeError as e:
        logger.error(f"✗ AttributeError (API issue): {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Langfuse API Fix Validation Test")
    logger.info("=" * 60)
    
    results = []
    
    # Test 1: Initialization
    results.append(("Initialization", test_langfuse_initialization()))
    
    # Test 2: Trace creation
    results.append(("Trace Creation", test_trace_creation()))
    
    # Test 3: Span creation
    results.append(("Span Creation", test_span_creation()))
    
    # Test 4: Generation creation
    results.append(("Generation Creation", test_generation_creation()))
    
    # Flush traces
    from utils import langfuse_tracer
    langfuse_tracer.flush()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("✓ All tests passed! Langfuse API fix is working correctly.")
        return 0
    else:
        logger.error("✗ Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
