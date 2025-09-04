import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

def debug_azure_config():
    """Debug Azure OpenAI configuration"""
    print("🔍 Debugging Azure OpenAI Configuration...")
    
    # Check all possible environment variable names
    env_vars_to_check = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
        "ENDPOINTS_KEY",  # Alternative name sometimes used
        "DEPLOYMENT_NAME"  # Alternative name
    ]
    
    print("📋 Environment variables found:")
    for var in env_vars_to_check:
        value = os.getenv(var)
        if value:
            if "KEY" in var:
                print(f"   ✅ {var}: Present ({len(value)} characters)")
            else:
                print(f"   ✅ {var}: {value}")
        else:
            print(f"   ❌ {var}: Not found")
    
    # Check .env file content
    print(f"\n📁 Content of {env_path}:")
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
            print(content)
    else:
        print("❌ .env file not found")
    
    # Suggested .env format
    print(f"\n💡 Suggested .env format:")
    print("AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
    print("AZURE_OPENAI_API_KEY=your-api-key-here")
    print("AZURE_OPENAI_DEPLOYMENT=your-deployment-name")
    print("AZURE_OPENAI_API_VERSION=2024-02-15-preview")

if __name__ == "__main__":
    debug_azure_config()