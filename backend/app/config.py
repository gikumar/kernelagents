# backend/app/config.py
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

print(f"📁 Loading .env from: {env_path}")
print(f"📁 .env file exists: {env_path.exists()}")

# ----- AZURE OPENAI CONFIGURATION -----
# Map your existing variables to the expected names
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("ENDPOINTS_KEY")  # Use ENDPOINTS_KEY as the API key
AZURE_OPENAI_DEPLOYMENT = os.getenv("DEPLOYMENT_NAME")  # Use DEPLOYMENT_NAME

# ----- DATABRICKS CONFIGURATION -----
DATABRICKS_SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_ACCESS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "trade_catalog")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "trade_schema")

# ----- YOUR EXISTING VARIABLES (for reference) -----
AZURE_AI_FOUNDRY_PROJECT_ENDPOINT = os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
AZURE_AI_SERVICES_ENDPOINT = os.getenv("AZURE_AI_SERVICES_ENDPOINT")
MODEL_ENDPOINT = os.getenv("MODEL_ENDPOINT")
MODEL_NAME = os.getenv("MODEL_NAME")
ENDPOINTS_KEY = os.getenv("ENDPOINTS_KEY")
AGENT_ID = os.getenv("AGENT_ID")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")

# ----- VALIDATION -----
def validate_config():
    """Validate that required configuration is present"""
    required_vars = [
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_ACCESS_TOKEN", 
        "DATABRICKS_HTTP_PATH",
    ]
    
    # Azure OpenAI is optional for basic functionality
    optional_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "ENDPOINTS_KEY",  # This becomes AZURE_OPENAI_KEY
        "DEPLOYMENT_NAME"  # This becomes AZURE_OPENAI_DEPLOYMENT
    ]
    
    missing_required = []
    for var in required_vars:
        if not globals().get(var):
            missing_required.append(var)
    
    if missing_required:
        raise ValueError(f"Missing required environment variables: {missing_required}")
    
    # Check if Azure OpenAI is fully configured
    azure_configured = all([
        os.getenv("AZURE_OPENAI_ENDPOINT"),
        os.getenv("ENDPOINTS_KEY"),
        os.getenv("DEPLOYMENT_NAME")
    ])
    
    if azure_configured:
        print("✅ Azure OpenAI fully configured")
    else:
        print("⚠️  Azure OpenAI not fully configured - some features may use simple mode")
    
    print("✅ Configuration validated successfully")

# Validate on import
try:
    validate_config()
except ValueError as e:
    print(f"❌ Configuration error: {e}")
    print("Please check your .env file")