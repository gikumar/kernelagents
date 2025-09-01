# backend/app/config.py (updated)
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

print(f"📁 Loading .env from: {env_path}")
print(f"📁 .env file exists: {env_path.exists()}")

# ----- AZURE OPENAI CONFIGURATION -----
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("ENDPOINTS_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") or os.getenv("DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# ----- DATABRICKS CONFIGURATION -----
DATABRICKS_SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_ACCESS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "trade_catalog")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "trade_schema")

# ----- VALIDATION -----
def validate_config():
    """Validate that required configuration is present"""
    # Azure OpenAI is required for LLM functionality
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT"
    ]
    
    # Databricks is optional but recommended for data queries
    optional_vars = [
        "DATABRICKS_SERVER_HOSTNAME",
        "DATABRICKS_ACCESS_TOKEN", 
        "DATABRICKS_HTTP_PATH"
    ]
    
    missing_required = []
    for var in required_vars:
        if not os.getenv(var.replace("AZURE_OPENAI_", "").replace("_", "").upper()) and not globals().get(var):
            missing_required.append(var)
    
    if missing_required:
        raise ValueError(f"Missing required Azure OpenAI environment variables: {missing_required}")
    
    # Check if Databricks is configured
    databricks_configured = all([
        os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        os.getenv("DATABRICKS_ACCESS_TOKEN"),
        os.getenv("DATABRICKS_HTTP_PATH")
    ])
    
    if databricks_configured:
        print("✅ Databricks fully configured for data queries")
    else:
        print("⚠️  Databricks not configured - data query features will be limited")
    
    print("✅ Configuration validated successfully")

# Validate on import
try:
    validate_config()
except ValueError as e:
    print(f"❌ Configuration error: {e}")
    print("Please check your .env file")