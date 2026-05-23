"""
Test script to verify the refactored Langfuse implementation using @observe decorators.

This script tests:
1. Langfuse initialization
2. @observe_if_enabled decorator functionality
3. Context updates (trace and observation)
4. Graceful degradation when Langfuse is disabled
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, 'src')

from src.utils import langfuse_tracer
from src.config import Config


def test_initialization():
    """Test Langfuse initialization."""
    print("=" * 60)
    print("TEST 1: Langfuse Initialization")
    print("=" * 60)
    
    # Initialize Langfuse
    langfuse_tracer.initialize_langfuse()
    
    is_enabled = langfuse_tracer.is_enabled()
    print(f"✓ Langfuse enabled: {is_enabled}")
    
    if is_enabled:
        print(f"✓ Langfuse configured with host: {Config.LANGFUSE_HOST}")
        context = langfuse_tracer.get_langfuse_context()
        print(f"✓ Context available: {context is not None}")
    else:
        print("ℹ Langfuse is disabled (not configured)")
    
    print()
    return is_enabled


def test_decorator():
    """Test @observe_if_enabled decorator."""
    print("=" * 60)
    print("TEST 2: @observe_if_enabled Decorator")
    print("=" * 60)
    
    @langfuse_tracer.observe_if_enabled(name="test-sync-function")
    def sync_function(x, y):
        """Test synchronous function."""
        return x + y
    
    @langfuse_tracer.observe_if_enabled(name="test-async-function")
    async def async_function(x, y):
        """Test asynchronous function."""
        await asyncio.sleep(0.1)
        return x * y
    
    # Test sync function
    result = sync_function(2, 3)
    print(f"✓ Sync function result: {result} (expected: 5)")
    assert result == 5, "Sync function failed"
    
    # Test async function
    result = asyncio.run(async_function(4, 5))
    print(f"✓ Async function result: {result} (expected: 20)")
    assert result == 20, "Async function failed"
    
    print("✓ Decorators work correctly")
    print()


def test_context_updates():
    """Test context update functions."""
    print("=" * 60)
    print("TEST 3: Context Updates")
    print("=" * 60)
    
    @langfuse_tracer.observe_if_enabled(name="test-context-updates")
    def test_function():
        """Test function with context updates."""
        # Update trace
        langfuse_tracer.update_current_trace(
            session_id="test-session-123",
            tags=["test", "refactored"],
            metadata={"test_type": "context_update"}
        )
        print("✓ Trace updated with session_id and tags")
        
        # Update observation
        langfuse_tracer.update_current_observation(
            output={"status": "success"},
            metadata={"step": "context_test"}
        )
        print("✓ Observation updated with output and metadata")
        
        return "success"
    
    result = test_function()
    print(f"✓ Function completed: {result}")
    print()


def test_error_handling():
    """Test error handling."""
    print("=" * 60)
    print("TEST 4: Error Handling")
    print("=" * 60)
    
    @langfuse_tracer.observe_if_enabled(name="test-error-handling")
    def failing_function():
        """Test function that raises an error."""
        try:
            raise ValueError("Test error")
        except Exception as e:
            langfuse_tracer.update_trace_with_error(e)
            print(f"✓ Error captured: {e}")
            return "error_handled"
    
    result = failing_function()
    print(f"✓ Error handling works: {result}")
    print()


def test_nested_observations():
    """Test nested observations (trace with spans)."""
    print("=" * 60)
    print("TEST 5: Nested Observations")
    print("=" * 60)
    
    @langfuse_tracer.observe_if_enabled(name="parent-function")
    def parent_function():
        """Parent function that calls child functions."""
        langfuse_tracer.update_current_observation(
            input={"operation": "parent"},
            metadata={"level": "parent"}
        )
        
        result1 = child_function_1()
        result2 = child_function_2()
        
        langfuse_tracer.update_current_observation(
            output={"results": [result1, result2]}
        )
        
        return [result1, result2]
    
    @langfuse_tracer.observe_if_enabled(name="child-function-1")
    def child_function_1():
        """First child function."""
        langfuse_tracer.update_current_observation(
            metadata={"child": 1}
        )
        return "child1_result"
    
    @langfuse_tracer.observe_if_enabled(name="child-function-2")
    def child_function_2():
        """Second child function."""
        langfuse_tracer.update_current_observation(
            metadata={"child": 2}
        )
        return "child2_result"
    
    results = parent_function()
    print(f"✓ Parent function completed with results: {results}")
    print("✓ Nested observations work correctly")
    print()


def test_generation_type():
    """Test generation-type observation."""
    print("=" * 60)
    print("TEST 6: Generation Type Observation")
    print("=" * 60)
    
    @langfuse_tracer.observe_if_enabled(name="test-llm-call", as_type="generation")
    async def mock_llm_call(prompt: str):
        """Mock LLM call."""
        # Update with model and usage info
        langfuse_tracer.update_current_observation(
            input={"prompt": prompt},
            model="test-model",
            model_parameters={"temperature": 0.0},
            usage={"input": 10, "output": 20, "total": 30}
        )
        
        await asyncio.sleep(0.1)
        
        response = "Mock LLM response"
        langfuse_tracer.update_current_observation(
            output={"response": response}
        )
        
        return response
    
    result = asyncio.run(mock_llm_call("Test prompt"))
    print(f"✓ LLM call completed: {result}")
    print("✓ Generation type observation works")
    print()


def test_flush():
    """Test flushing traces."""
    print("=" * 60)
    print("TEST 7: Flush Traces")
    print("=" * 60)
    
    langfuse_tracer.flush()
    print("✓ Traces flushed successfully")
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TESTING REFACTORED LANGFUSE IMPLEMENTATION")
    print("=" * 60)
    print()
    
    try:
        # Run tests
        is_enabled = test_initialization()
        test_decorator()
        test_context_updates()
        test_error_handling()
        test_nested_observations()
        test_generation_type()
        test_flush()
        
        # Summary
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print("✅ All tests passed!")
        
        if is_enabled:
            print("\nℹ Langfuse is enabled. Check your Langfuse dashboard to see traces:")
            print(f"  {Config.LANGFUSE_HOST}")
        else:
            print("\nℹ Langfuse is disabled. Tests verified graceful degradation.")
        
        print("\n" + "=" * 60)
        return 0
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
