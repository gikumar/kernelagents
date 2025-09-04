# backend/test_different_api_versions.py
import os
import sys
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

def test_api_versions():
    """Test different API versions to find one that works"""
    print("🧪 Testing Different API Versions...")
    
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip('/')
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    if not all([endpoint, api_key, deployment]):
        print("❌ Missing configuration")
        return
    
    # Common API versions to try
    api_versions_to_test = [
        "2024-02-15-preview",  # Most common
        "2024-08-01-preview",
        "2024-11-20",          # Your current version
        "2024-10-01-preview",
        "2024-07-01-preview",
        "2024-05-01-preview",
        "2024-03-01-preview"
    ]
    
    for api_version in api_versions_to_test:
        print(f"\n🔧 Testing API Version: {api_version}")
        try:
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version
            )
            
            # Quick test
            response = client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            
            print(f"   ✅ SUCCESS with {api_version}")
            print(f"   💬 Response: {response.choices[0].message.content}")
            print(f"   💡 Recommended: Use API version {api_version}")
            break
            
        except Exception as e:
            print(f"   ❌ FAILED with {api_version}: {str(e)[:100]}...")

if __name__ == "__main__":
    test_api_versions() 