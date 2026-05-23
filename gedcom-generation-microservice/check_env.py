"""
Simple script to check if environment variables are loaded correctly.
Run this from the gedcom-generation-microservice directory.
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check API key
api_key = os.getenv('OPENROUTER_API_KEY', '')

print("=" * 60)
print("Environment Variable Check")
print("=" * 60)
print(f"API Key present: {'Yes' if api_key else 'No'}")
print(f"API Key length: {len(api_key)}")
if api_key:
    print(f"API Key starts with: {api_key[:15]}..." if len(api_key) > 15 else f"API Key: {api_key}")
    print(f"API Key format looks valid: {'Yes' if api_key.startswith('sk-or-v1-') else 'No (should start with sk-or-v1-)'}")
else:
    print("ERROR: OPENROUTER_API_KEY is not set!")
    print("\nPlease ensure:")
    print("1. You have a .env file in the gedcom-generation-microservice directory")
    print("2. The .env file contains: OPENROUTER_API_KEY=sk-or-v1-your-actual-key")
    print("3. The API key is valid from https://openrouter.ai/keys")
print("=" * 60)
