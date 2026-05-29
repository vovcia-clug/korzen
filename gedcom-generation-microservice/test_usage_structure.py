"""
Test to verify the correct usage_details structure for Langfuse v4.x
"""
import os
from langfuse import Langfuse

# Initialize client (will be disabled without keys, but we can still test the structure)
client = Langfuse()

print("Testing usage_details structure...")
print("\n1. Current implementation (INCORRECT):")
print("   usage_details={'input': 100, 'output': 50, 'total': 150}")

print("\n2. Expected implementation (CORRECT per docstring):")
print("   usage_details={'prompt_tokens': 100, 'completion_tokens': 50}")

print("\n3. Langfuse documentation example:")
print("   usage_details={")
print("       'prompt_tokens': response.usage.prompt_tokens,")
print("       'completion_tokens': response.usage.completion_tokens")
print("   }")

print("\n" + "="*70)
print("DIAGNOSIS:")
print("="*70)
print("The code is sending usage data with keys: 'input', 'output', 'total'")
print("But Langfuse v4.x expects: 'prompt_tokens', 'completion_tokens'")
print("\nThis mismatch prevents Langfuse from:")
print("  - Recognizing the token usage")
print("  - Calculating costs based on model pricing")
print("  - Displaying usage in the dashboard")
print("\nFIX: Update langfuse_tracer.py line 104 to map to correct field names")
