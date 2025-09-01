# backend/app/config.py
from dotenv import load_dotenv
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger.info(f"Loading .env from: {env_path}")
logger.info(f".env file exists: {env_path.exists()}")

# ----- AZURE OPENAI CONFIGURATION -----
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT") 
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# ----- DATABRICKS CONFIGURATION -----
DATABRICKS_SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
DATABRICKS_ACCESS_TOKEN = os.getenv("DATABRICKS_ACCESS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_CATALOG = os.getenv("DATABRICKS_CATALOG", "trade_catalog")
DATABRICKS_SCHEMA = os.getenv("DATABRICKS_SCHEMA", "trade_schema")

def validate_config():
    """Validate that required configuration is present"""
    config_status = {
        "azure_openai": False,
        "databricks": False,
        "errors": [],
        "warnings": []
    }
    
    # Check Azure OpenAI configuration
    required_azure_vars = {
        "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
        "AZURE_OPENAI_API_KEY": AZURE_OPENAI_KEY,
        "AZURE_OPENAI_DEPLOYMENT": AZURE_OPENAI_DEPLOYMENT
    }
    
    missing_azure = []
    for var_name, var_value in required_azure_vars.items():
        if not var_value:
            missing_azure.append(var_name)
        elif var_name == "AZURE_OPENAI_ENDPOINT" and not var_value.startswith("https://"):
            config_status["warnings"].append(f"{var_name} should start with 'https://'")
    
    if missing_azure:
        config_status["errors"].append(f"Missing Azure OpenAI variables: {missing_azure}")
    else:
        config_status["azure_openai"] = True
        logger.info("Azure OpenAI configuration validated")
    
    # Check Databricks configuration
    required_databricks_vars = {
        "DATABRICKS_SERVER_HOSTNAME": DATABRICKS_SERVER_HOSTNAME,
        "DATABRICKS_ACCESS_TOKEN": DATABRICKS_ACCESS_TOKEN,
        "DATABRICKS_HTTP_PATH": DATABRICKS_HTTP_PATH
    }
    
    missing_databricks = []
    for var_name, var_value in required_databricks_vars.items():
        if not var_value:
            missing_databricks.append(var_name)
    
    if missing_databricks:
        config_status["warnings"].append(f"Databricks not configured - missing: {missing_databricks}")
    else:
        config_status["databricks"] = True
        logger.info("Databricks configuration validated")
    
    # Log status
    if config_status["azure_openai"]:
        logger.info("✅ Azure OpenAI fully configured")
    else:
        logger.error("❌ Azure OpenAI not configured properly")
    
    if config_status["databricks"]:
        logger.info("✅ Databricks fully configured for data queries")
    else:
        logger.warning("⚠️ Databricks not configured - data query features will be limited")
    
    # Report any errors or warnings
    for error in config_status["errors"]:
        logger.error(f"Configuration error: {error}")
    
    for warning in config_status["warnings"]:
        logger.warning(f"Configuration warning: {warning}")
    
    return config_status

def get_config_summary():
    """Get a summary of current configuration"""
    return {
        "azure_openai": {
            "endpoint": AZURE_OPENAI_ENDPOINT[:50] + "..." if AZURE_OPENAI_ENDPOINT and len(AZURE_OPENAI_ENDPOINT) > 50 else AZURE_OPENAI_ENDPOINT,
            "api_key": "***" + AZURE_OPENAI_KEY[-4:] if AZURE_OPENAI_KEY and len(AZURE_OPENAI_KEY) > 4 else "Not set",
            "deployment": AZURE_OPENAI_DEPLOYMENT,
            "api_version": AZURE_OPENAI_API_VERSION
        },
        "databricks": {
            "hostname": DATABRICKS_SERVER_HOSTNAME,
            "access_token": "***" + DATABRICKS_ACCESS_TOKEN[-4:] if DATABRICKS_ACCESS_TOKEN and len(DATABRICKS_ACCESS_TOKEN) > 4 else "Not set",
            "http_path": DATABRICKS_HTTP_PATH,
            "catalog": DATABRICKS_CATALOG,
            "schema": DATABRICKS_SCHEMA
        }
    }

# Validate configuration on import
config_status = validate_config()

# Make validation results available
CONFIG_VALID = config_status["azure_openai"] and config_status["databricks"]
AZURE_OPENAI_VALID = config_status["azure_openai"]
DATABRICKS_VALID = config_status["databricks"]