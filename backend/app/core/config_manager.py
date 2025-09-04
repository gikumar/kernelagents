# backend/app/core/config_manager.py
import os
from dotenv import load_dotenv
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger.info(f"Loading .env from: {env_path}")
logger.info(f".env file exists: {env_path.exists()}")

class Config:
    """Central configuration management with validation"""
    
    def __init__(self):
        self._config_status = {
            "azure_openai": False,
            "databricks": False,
            "errors": [],
            "warnings": []
        }
        self.validate_config()
    
    @property
    def AZURE_OPENAI_ENDPOINT(self):
        return os.getenv("AZURE_OPENAI_ENDPOINT")
    
    @property
    def AZURE_OPENAI_KEY(self):
        return os.getenv("AZURE_OPENAI_API_KEY")
    
    @property
    def AZURE_OPENAI_DEPLOYMENT(self):
        return os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    @property
    def AZURE_OPENAI_API_VERSION(self):
        return os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    
    @property
    def DATABRICKS_SERVER_HOSTNAME(self):
        return os.getenv("DATABRICKS_SERVER_HOSTNAME")
    
    @property
    def DATABRICKS_ACCESS_TOKEN(self):
        return os.getenv("DATABRICKS_ACCESS_TOKEN")
    
    @property
    def DATABRICKS_HTTP_PATH(self):
        return os.getenv("DATABRICKS_HTTP_PATH")
    
    @property
    def DATABRICKS_CATALOG(self):
        return os.getenv("DATABRICKS_CATALOG", "trade_catalog")
    
    @property
    def DATABRICKS_SCHEMA(self):
        return os.getenv("DATABRICKS_SCHEMA", "trade_schema")
    
    def validate_config(self):
        """Validate that required configuration is present"""
        # Reset status
        self._config_status = {
            "azure_openai": False,
            "databricks": False,
            "errors": [],
            "warnings": []
        }
        
        # Check Azure OpenAI configuration
        required_azure_vars = {
            "AZURE_OPENAI_ENDPOINT": self.AZURE_OPENAI_ENDPOINT,
            "AZURE_OPENAI_API_KEY": self.AZURE_OPENAI_KEY,
            "AZURE_OPENAI_DEPLOYMENT": self.AZURE_OPENAI_DEPLOYMENT
        }
        
        missing_azure = []
        for var_name, var_value in required_azure_vars.items():
            if not var_value:
                missing_azure.append(var_name)
            elif var_name == "AZURE_OPENAI_ENDPOINT" and not var_value.startswith("https://"):
                self._config_status["warnings"].append(f"{var_name} should start with 'https://'")
        
        if missing_azure:
            self._config_status["errors"].append(f"Missing Azure OpenAI variables: {missing_azure}")
        else:
            self._config_status["azure_openai"] = True
            logger.info("Azure OpenAI configuration validated")
        
        # Check Databricks configuration
        required_databricks_vars = {
            "DATABRICKS_SERVER_HOSTNAME": self.DATABRICKS_SERVER_HOSTNAME,
            "DATABRICKS_ACCESS_TOKEN": self.DATABRICKS_ACCESS_TOKEN,
            "DATABRICKS_HTTP_PATH": self.DATABRICKS_HTTP_PATH
        }
        
        missing_databricks = []
        for var_name, var_value in required_databricks_vars.items():
            if not var_value:
                missing_databricks.append(var_name)
        
        if missing_databricks:
            self._config_status["warnings"].append(f"Databricks not configured - missing: {missing_databricks}")
        else:
            self._config_status["databricks"] = True
            logger.info("Databricks configuration validated")
        
        # Log status
        if self._config_status["azure_openai"]:
            logger.info("✅ Azure OpenAI fully configured")
        else:
            logger.error("❌ Azure OpenAI not configured properly")
        
        if self._config_status["databricks"]:
            logger.info("✅ Databricks fully configured for data queries")
        else:
            logger.warning("⚠️ Databricks not configured - data query features will be limited")
        
        # Report any errors or warnings
        for error in self._config_status["errors"]:
            logger.error(f"Configuration error: {error}")
        
        for warning in self._config_status["warnings"]:
            logger.warning(f"Configuration warning: {warning}")
        
        return self._config_status
    
    def get_config_summary(self):
        """Get a summary of current configuration"""
        return {
            "azure_openai": {
                "endpoint": self.AZURE_OPENAI_ENDPOINT[:50] + "..." if self.AZURE_OPENAI_ENDPOINT and len(self.AZURE_OPENAI_ENDPOINT) > 50 else self.AZURE_OPENAI_ENDPOINT,
                "api_key": "***" + self.AZURE_OPENAI_KEY[-4:] if self.AZURE_OPENAI_KEY and len(self.AZURE_OPENAI_KEY) > 4 else "Not set",
                "deployment": self.AZURE_OPENAI_DEPLOYMENT,
                "api_version": self.AZURE_OPENAI_API_VERSION
            },
            "databricks": {
                "hostname": self.DATABRICKS_SERVER_HOSTNAME,
                "access_token": "***" + self.DATABRICKS_ACCESS_TOKEN[-4:] if self.DATABRICKS_ACCESS_TOKEN and len(self.DATABRICKS_ACCESS_TOKEN) > 4 else "Not set",
                "http_path": self.DATABRICKS_HTTP_PATH,
                "catalog": self.DATABRICKS_CATALOG,
                "schema": self.DATABRICKS_SCHEMA
            }
        }
    
    @property
    def config_valid(self):
        """Check if both Azure OpenAI and Databricks are configured"""
        return self._config_status["azure_openai"] and self._config_status["databricks"]
    
    @property
    def azure_openai_valid(self):
        """Check if Azure OpenAI is configured"""
        return self._config_status["azure_openai"]
    
    @property
    def databricks_valid(self):
        """Check if Databricks is configured"""
        return self._config_status["databricks"]
    
    @property
    def errors(self):
        """Get configuration errors"""
        return self._config_status["errors"]
    
    @property
    def warnings(self):
        """Get configuration warnings"""
        return self._config_status["warnings"]

# Global config instance
config = Config()

# Make legacy variables available for backward compatibility
# (This helps during the transition period)
AZURE_OPENAI_ENDPOINT = config.AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_KEY = config.AZURE_OPENAI_KEY
AZURE_OPENAI_DEPLOYMENT = config.AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_API_VERSION = config.AZURE_OPENAI_API_VERSION
DATABRICKS_SERVER_HOSTNAME = config.DATABRICKS_SERVER_HOSTNAME
DATABRICKS_ACCESS_TOKEN = config.DATABRICKS_ACCESS_TOKEN
DATABRICKS_HTTP_PATH = config.DATABRICKS_HTTP_PATH
DATABRICKS_CATALOG = config.DATABRICKS_CATALOG
DATABRICKS_SCHEMA = config.DATABRICKS_SCHEMA
CONFIG_VALID = config.config_valid
AZURE_OPENAI_VALID = config.azure_openai_valid
DATABRICKS_VALID = config.databricks_valid