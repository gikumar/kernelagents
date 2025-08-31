# backend/app/schema_utils.py

import os
import json
from pathlib import Path
import logging

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Schema file path
SCHEMA_FILE = Path(__file__).parent / "cache" / "databricks_schema.json"

def load_schema() -> dict:
    """Load schema from cache file, auto-refresh if not found"""
    logger.info(f"📋 Loading schema from: {SCHEMA_FILE}")
    
    try:
        if not SCHEMA_FILE.exists():
            logger.warning("❌ Schema cache file does not exist, attempting to refresh...")
            # Auto-refresh if schema file doesn't exist
            return refresh_schema()
        
        with open(SCHEMA_FILE, "r") as f:
            schema = json.load(f)
        
        logger.info(f"✅ Loaded schema with {len(schema)} tables")
        return schema
        
    except Exception as e:
        logger.error(f"❌ Error loading schema: {str(e)}")
        # Try to refresh if loading fails
        try:
            return refresh_schema()
        except:
            return {}

def refresh_schema():
    """Refresh schema by fetching from Databricks"""
    logger.info("🔄 Refreshing schema from Databricks...")
    
    try:
        # Use absolute import instead of relative
        from schema_loader import fetch_schema_from_databricks
        schema = fetch_schema_from_databricks()
        
        if schema:
            logger.info(f"✅ Schema refreshed with {len(schema)} tables")
            return schema
        else:
            logger.error("❌ Failed to refresh schema")
            # Return empty dict if refresh fails
            return {}
    except Exception as e:
        logger.error(f"❌ Error refreshing schema: {str(e)}")
        return {}

def get_table_columns(table_name: str) -> list:
    """Get columns for a specific table"""
    schema = load_schema()
    table_key = table_name.lower()
    return schema.get(table_key, [])

def list_tables() -> list:
    """List all available tables"""
    schema = load_schema()
    return list(schema.keys())