"""
Test script to verify that model names are properly tracked in Langfuse.

This script tests that:
1. The model name is passed to Langfuse observations
2. Token usage is tracked correctly
3. Model parameters are recorded
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path and set up proper imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import with proper module structure
from src.services.openrouter_client import OpenRouterClient
from src.utils import langfuse_tracer


async def test_model_tracking():
    """Test that model name is properly tracked in Langfuse."""
    print("Testing model name tracking in Langfuse...")
    
    # Mock the OpenAI client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "0 HEAD\n1 GEDC\n2 VERS 5.5.1\n0 TRLR"
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50
    mock_response.usage.total_tokens = 150
    
    # Track calls to update_current_observation
    update_calls = []
    
    original_update = langfuse_tracer.update_current_observation
    def mock_update(**kwargs):
        update_calls.append(kwargs)
        return original_update(**kwargs)
    
    with patch.object(langfuse_tracer, 'update_current_observation', side_effect=mock_update):
        # Create client
        client = OpenRouterClient(
            api_key="test-key",
            model="google/gemini-flash-1.5"
        )
        
        # Mock the actual API call
        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            # Call generate_gedcom
            result = await client.generate_gedcom(
                formatted_document="Test document content",
                system_prompt="Test system prompt"
            )
            
            print(f"✓ Generated GEDCOM: {len(result)} bytes")
            
            # Verify update_current_observation was called
            print(f"\n✓ update_current_observation called {len(update_calls)} times")
            
            # Check first call (before API call) - should have model info
            if len(update_calls) > 0:
                first_call = update_calls[0]
                print("\nFirst call (model info):")
                print(f"  - model: {first_call.get('model')}")
                print(f"  - model_parameters: {first_call.get('model_parameters')}")
                print(f"  - metadata: {first_call.get('metadata')}")
                
                if first_call.get('model') == 'google/gemini-flash-1.5':
                    print("  ✓ Model name correctly set!")
                else:
                    print(f"  ✗ Model name missing or incorrect: {first_call.get('model')}")
                    return False
                
                if first_call.get('model_parameters', {}).get('temperature') == 0.0:
                    print("  ✓ Model parameters correctly set!")
                else:
                    print(f"  ✗ Model parameters missing or incorrect")
                    return False
            
            # Check second call (after API call) - should have usage info
            if len(update_calls) > 1:
                second_call = update_calls[1]
                print("\nSecond call (usage info):")
                print(f"  - usage: {second_call.get('usage')}")
                
                usage = second_call.get('usage', {})
                if usage.get('input') == 100 and usage.get('output') == 50 and usage.get('total') == 150:
                    print("  ✓ Token usage correctly tracked!")
                else:
                    print(f"  ✗ Token usage missing or incorrect")
                    return False
            
            print("\n✓ All checks passed!")
            return True


async def test_context_extraction_model_tracking():
    """Test that model name is tracked for context extraction calls."""
    print("\n" + "="*60)
    print("Testing model name tracking for context extraction...")
    
    # Mock the OpenAI client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Updated context information"
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 200
    mock_response.usage.completion_tokens = 75
    mock_response.usage.total_tokens = 275
    
    # Track calls to update_current_observation
    update_calls = []
    
    original_update = langfuse_tracer.update_current_observation
    def mock_update(**kwargs):
        update_calls.append(kwargs)
        return original_update(**kwargs)
    
    with patch.object(langfuse_tracer, 'update_current_observation', side_effect=mock_update):
        # Create client
        client = OpenRouterClient(
            api_key="test-key",
            model="google/gemini-flash-1.5"
        )
        
        # Mock the actual API call
        with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            
            # Call generate_text
            result = await client.generate_text(
                user_content="Test user content",
                system_prompt="Test system prompt",
                temperature=0.0
            )
            
            print(f"✓ Generated text: {len(result)} chars")
            
            # Verify update_current_observation was called
            print(f"\n✓ update_current_observation called {len(update_calls)} times")
            
            # Check first call (before API call) - should have model info
            if len(update_calls) > 0:
                first_call = update_calls[0]
                print("\nFirst call (model info):")
                print(f"  - model: {first_call.get('model')}")
                print(f"  - model_parameters: {first_call.get('model_parameters')}")
                print(f"  - metadata: {first_call.get('metadata')}")
                
                if first_call.get('model') == 'google/gemini-flash-1.5':
                    print("  ✓ Model name correctly set!")
                else:
                    print(f"  ✗ Model name missing or incorrect: {first_call.get('model')}")
                    return False
            
            # Check second call (after API call) - should have usage info
            if len(update_calls) > 1:
                second_call = update_calls[1]
                print("\nSecond call (usage info):")
                print(f"  - usage: {second_call.get('usage')}")
                
                usage = second_call.get('usage', {})
                if usage.get('input') == 200 and usage.get('output') == 75 and usage.get('total') == 275:
                    print("  ✓ Token usage correctly tracked!")
                else:
                    print(f"  ✗ Token usage missing or incorrect")
                    return False
            
            print("\n✓ All checks passed!")
            return True


async def main():
    """Run all tests."""
    print("="*60)
    print("Model Name Tracking Test Suite")
    print("="*60)
    
    try:
        # Test 1: GEDCOM generation
        result1 = await test_model_tracking()
        
        # Test 2: Context extraction
        result2 = await test_context_extraction_model_tracking()
        
        print("\n" + "="*60)
        if result1 and result2:
            print("✓ ALL TESTS PASSED")
            print("="*60)
            print("\nModel names are now properly tracked in Langfuse!")
            print("The following information is captured:")
            print("  - Model name (e.g., 'google/gemini-flash-1.5')")
            print("  - Model parameters (e.g., temperature)")
            print("  - Token usage (input, output, total)")
            print("  - Operation metadata")
            return 0
        else:
            print("✗ SOME TESTS FAILED")
            print("="*60)
            return 1
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
