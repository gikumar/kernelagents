# backend/app/schema_loader.py

import os
import json
import databricks.sql
from databricks.sql.exc import OperationalError
import logging
from pathlib import Path

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

# Get the absolute path to the schema file
SCHEMA_FILE = Path(__file__).parent / "cache" / "databricks_schema.json"

def fetch_schema_from_databricks():
    """Fetch schema from Databricks and save to cache"""
    try:
        # Use absolute import
        from config import (
            DATABRICKS_SERVER_HOSTNAME,
            DATABRICKS_ACCESS_TOKEN,
            DATABRICKS_HTTP_PATH
        )
        
        logger.info(f"🚀 Fetching schema from Databricks: {DATABRICKS_SERVER_HOSTNAME}")
        
        with databricks.sql.connect(
            server_hostname=DATABRICKS_SERVER_HOSTNAME,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_ACCESS_TOKEN
        ) as conn:
            cursor = conn.cursor()

            # Get all tables in the schema
            cursor.execute("SHOW TABLES IN trade_catalog.trade_schema")
            tables = cursor.fetchall()

            schema_dict = {}

            # For each table, get columns
            for table_row in tables:
                table_name = table_row[1]  # Second column is table name
                full_table_name = f"trade_catalog.trade_schema.{table_name}"

                cursor.execute(f"DESCRIBE TABLE {full_table_name}")
                column_rows = cursor.fetchall()
                # Get only column names (first element of each row)
                column_names = [row[0] for row in column_rows if row[0] and not row[0].startswith("#")]

                schema_dict[table_name.lower()] = column_names

            # Ensure cache directory exists
            SCHEMA_FILE.parent.mkdir(exist_ok=True)
            
            # Write to JSON file
            with open(SCHEMA_FILE, "w") as f:
                json.dump(schema_dict, f, indent=2)

            logger.info(f"✅ Schema successfully written to {SCHEMA_FILE}")
            return schema_dict

    except OperationalError as e:
        logger.error(f"❌ Databricks connection failed: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return None

def load_schema_from_cache():
    """Load schema from cache file"""
    try:
        if SCHEMA_FILE.exists():
            with open(SCHEMA_FILE, "r") as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"❌ Error loading schema from cache: {e}")
        return None

def get_table_columns():
    """Get table columns, fetching from Databricks if cache doesn't exist"""
    # Try to load from cache first
    schema = load_schema_from_cache()
    
    # If cache doesn't exist or is empty, fetch from Databricks
    if not schema:
        logger.info("📋 Cache not found, fetching from Databricks...")
        schema = fetch_schema_from_databricks()
    
    return schema or {}