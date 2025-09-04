# backend/check_azure_config.py
import os
import sys
from pathlib import Path
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

def check_azure_config():
    """Check Azure OpenAI configuration"""
    print("🔍 Checking Azure OpenAI Configuration...")
    
    # Get all relevant environment variables
    config_vars = {
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_DEPLOYMENT": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    }
    
    # Print configuration
    for key, value in config_vars.items():
        if value:
            if "KEY" in key:
                print(f"✅ {key}: Present ({len(value)} characters)")
            else:
                print(f"✅ {key}: {value}")
        else:
            print(f"❌ {key}: Missing")
    
    # Try to connect to Azure OpenAI
    print("\n🔗 Testing Azure OpenAI connection...")
    try:
        client = AzureOpenAI(
            azure_endpoint=config_vars["AZURE_OPENAI_ENDPOINT"],
            api_key=config_vars["AZURE_OPENAI_API_KEY"],
            api_version=config_vars["AZURE_OPENAI_API_VERSION"]
        )
        
        # Test with a simple completion
        response = client.chat.completions.create(
            model=config_vars["AZURE_OPENAI_DEPLOYMENT"],
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            max_tokens=10
        )
        
        print(f"✅ Connection successful! Response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        
        # Provide troubleshooting tips
        print("\n🔧 Troubleshooting tips:")
        print("1. Check if your Azure OpenAI resource is active in Azure Portal")
        print("2. Verify the endpoint URL format: https://{resource-name}.openai.azure.com/")
        print("3. Ensure the deployment name matches exactly")
        print("4. Check if the API key is valid and has not expired")
        print("5. Verify the API version is supported")

if __name__ == "__main__":
    check_azure_config()