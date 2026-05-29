"""
Test script for Langfuse refactoring: spans and error logging.

This script tests:
1. Document group span creation with metadata
2. Error logging to Langfuse with context
3. Integration with existing tracing
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.utils import langfuse_tracer
from src.services.document_grouper import DocumentGrouper, DocumentGroup


def test_span_creation():
    """Test creating spans with metadata."""
    print("\n=== Testing Span Creation ===")
    
    if not langfuse_tracer.is_available():
        print("⚠️  Langfuse not available - spans will be no-ops")
    else:
        print("✓ Langfuse is available")
    
    # Test span creation with metadata
    test_metadata = {
        "document_id": "test-doc-123",
        "num_pages": 5,
        "expected_pages": 5,
        "completion_reason": "all_pages_received",
        "document_title": "Test Document",
        "location": "Test Location",
        "date_range": "1900-1950"
    }
    
    print(f"\nCreating span with metadata: {test_metadata}")
    
    with langfuse_tracer.create_span("test-document-group", metadata=test_metadata) as span:
        print("✓ Span created successfully")
        print(f"  Span context: {span}")
        
        # Simulate some work
        import time
        time.sleep(0.1)
    
    print("✓ Span closed successfully")


def test_error_logging():
    """Test error logging to Langfuse."""
    print("\n=== Testing Error Logging ===")
    
    if not langfuse_tracer.is_available():
        print("⚠️  Langfuse not available - error logging will be no-ops")
    else:
        print("✓ Langfuse is available")
    
    # Test 1: Log a simple error
    print("\n1. Testing simple error logging:")
    try:
        raise ValueError("Test error message")
    except Exception as e:
        langfuse_tracer.log_error(
            e,
            context={
                "operation": "test_operation",
                "test_id": "test-123"
            }
        )
        print(f"✓ Logged error: {type(e).__name__}: {e}")
    
    # Test 2: Log error with detailed context
    print("\n2. Testing error with detailed context:")
    try:
        raise RuntimeError("API call failed")
    except Exception as e:
        langfuse_tracer.log_error(
            e,
            context={
                "document_id": "doc-456",
                "operation": "openrouter_api_call",
                "model": "google/gemini-flash-1.5",
                "attempt": 3,
                "max_retries": 3
            },
            level="ERROR"
        )
        print(f"✓ Logged error with context: {type(e).__name__}: {e}")
    
    # Test 3: Log warning-level error
    print("\n3. Testing warning-level error:")
    try:
        raise ValueError("Missing pages: [3, 5]")
    except Exception as e:
        langfuse_tracer.log_error(
            e,
            context={
                "document_id": "doc-789",
                "operation": "page_completeness_check",
                "missing_pages": [3, 5],
                "expected_pages": 10,
                "received_pages": [1, 2, 4, 6, 7, 8, 9, 10]
            },
            level="WARNING"
        )
        print(f"✓ Logged warning: {type(e).__name__}: {e}")


def test_document_grouper_error_handling():
    """Test error handling in DocumentGrouper."""
    print("\n=== Testing DocumentGrouper Error Handling ===")
    
    grouper = DocumentGrouper(timeout_seconds=10)
    
    # Test 1: Missing document_id
    print("\n1. Testing missing document_id error:")
    try:
        grouper.add_message({
            "metadata": {},  # Missing document_id
            "ocr_result": {"text": "test"}
        })
        print("✗ Should have raised ValueError")
    except ValueError as e:
        print(f"✓ Correctly raised ValueError: {e}")
    
    # Test 2: Valid message
    print("\n2. Testing valid message:")
    try:
        grouper.add_message({
            "metadata": {
                "document_id": "test-doc-001",
                "page_number": 1,
                "total_pages": 3
            },
            "ocr_result": {"text": "Page 1 content"}
        })
        print("✓ Message added successfully")
        
        # Check group was created
        group = grouper.get_group("test-doc-001")
        if group:
            print(f"✓ Group created with {len(group.messages)} message(s)")
        else:
            print("✗ Group not found")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


@langfuse_tracer.observe(name="test-traced-function")
async def test_traced_function_with_error():
    """Test a traced function that logs errors."""
    print("\n=== Testing Traced Function with Error Logging ===")
    
    try:
        # Simulate some work
        await asyncio.sleep(0.1)
        
        # Simulate an error
        raise RuntimeError("Simulated error in traced function")
        
    except Exception as e:
        print(f"✓ Caught error: {type(e).__name__}: {e}")
        
        # Log to Langfuse
        langfuse_tracer.log_error(
            e,
            context={
                "function": "test_traced_function_with_error",
                "operation": "simulated_work"
            }
        )
        print("✓ Error logged to Langfuse")
        
        # Re-raise to test error propagation
        raise


@langfuse_tracer.observe(name="test-nested-spans")
async def test_nested_spans():
    """Test nested spans with error logging."""
    print("\n=== Testing Nested Spans ===")
    
    # Outer span (from @observe decorator)
    print("✓ Outer span created by @observe decorator")
    
    # Inner span with create_span
    with langfuse_tracer.create_span(
        "inner-operation",
        metadata={"step": "processing", "item_count": 5}
    ):
        print("✓ Inner span created with create_span()")
        
        # Simulate work
        await asyncio.sleep(0.1)
        
        # Log an error within the span
        try:
            raise ValueError("Error in inner span")
        except Exception as e:
            langfuse_tracer.log_error(
                e,
                context={"location": "inner_span", "step": "processing"}
            )
            print(f"✓ Error logged within inner span: {e}")
    
    print("✓ Inner span closed")
    print("✓ Outer span will close when function returns")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Langfuse Refactoring Test Suite")
    print("=" * 60)
    
    # Check Langfuse availability
    if langfuse_tracer.is_available():
        print("\n✓ Langfuse is available and ready")
        client = langfuse_tracer.get_client()
        if client:
            print("✓ Langfuse client initialized")
    else:
        print("\n⚠️  Langfuse is not available - tests will run with no-op implementations")
    
    # Run tests
    test_span_creation()
    test_error_logging()
    test_document_grouper_error_handling()
    
    # Test traced functions
    try:
        await test_traced_function_with_error()
    except RuntimeError:
        print("✓ Error propagated correctly from traced function")
    
    await test_nested_spans()
    
    # Flush traces
    print("\n=== Flushing Langfuse Traces ===")
    langfuse_tracer.flush()
    print("✓ Traces flushed")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    
    if langfuse_tracer.is_available():
        print("\n📊 Check your Langfuse dashboard to see:")
        print("  - Document group spans with metadata")
        print("  - Error logs with context information")
        print("  - Nested span hierarchy")
        print("  - Stack traces for errors")
    else:
        print("\n⚠️  To see results in Langfuse, ensure:")
        print("  1. Langfuse is installed: pip install langfuse")
        print("  2. Environment variables are set:")
        print("     - LANGFUSE_PUBLIC_KEY")
        print("     - LANGFUSE_SECRET_KEY")
        print("     - LANGFUSE_HOST (optional)")


if __name__ == "__main__":
    asyncio.run(main())
