# backend/app/schema_utils.py
import os
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Schema file path
SCHEMA_FILE = Path(__file__).parent / "cache" / "databricks_schema.json"

def load_schema() -> dict:
    """Load schema from cache file, auto-refresh if not found or invalid"""
    logger.info(f"Loading schema from: {SCHEMA_FILE}")
    
    try:
        # Ensure cache directory exists
        SCHEMA_FILE.parent.mkdir(exist_ok=True)
        
        # Check if cache file exists and is valid
        if SCHEMA_FILE.exists():
            with open(SCHEMA_FILE, "r") as f:
                schema = json.load(f)
            
            # Validate schema structure
            if isinstance(schema, dict) and len(schema) > 0:
                logger.info(f"Loaded schema with {len(schema)} tables from cache")
                return schema
            else:
                logger.warning("Schema cache exists but appears invalid")
        
        # If no valid cache, try to refresh
        logger.info("No valid schema cache found, attempting to refresh from Databricks")
        return refresh_schema()
        
    except Exception as e:
        logger.error(f"Error loading schema: {str(e)}")
        # Return empty dict if everything fails
        return {}

def refresh_schema() -> dict:
    """Refresh schema by fetching from Databricks"""
    logger.info("Refreshing schema from Databricks...")
    
    try:
        # Import here to avoid circular dependencies
        schema = fetch_schema_from_databricks()
        
        if schema:
            logger.info(f"Schema refreshed with {len(schema)} tables")
            return schema
        else:
            logger.error("Failed to refresh schema from Databricks")
            # Try to load from hardcoded schema as fallback
            return load_hardcoded_schema()
    
    except Exception as e:
        logger.error(f"Error refreshing schema: {str(e)}")
        # Try hardcoded schema as last resort
        return load_hardcoded_schema()

def fetch_schema_from_databricks() -> dict:
    """Fetch schema from Databricks and save to cache"""
    try:
        from config import (
            DATABRICKS_SERVER_HOSTNAME,
            DATABRICKS_ACCESS_TOKEN,
            DATABRICKS_HTTP_PATH,
            DATABRICKS_CATALOG,
            DATABRICKS_SCHEMA,
            DATABRICKS_VALID
        )
        
        if not DATABRICKS_VALID:
            logger.error("Databricks configuration not valid")
            return {}
        
        try:
            import databricks.sql
        except ImportError:
            logger.error("databricks-sql-connector not installed")
            return {}
        
        logger.info(f"Connecting to Databricks: {DATABRICKS_SERVER_HOSTNAME}")
        
        with databricks.sql.connect(
            server_hostname=DATABRICKS_SERVER_HOSTNAME,
            http_path=DATABRICKS_HTTP_PATH,
            access_token=DATABRICKS_ACCESS_TOKEN
        ) as conn:
            cursor = conn.cursor()
            
            # Get all tables in the schema
            try:
                cursor.execute(f"SHOW TABLES IN {DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}")
                tables = cursor.fetchall()
            except Exception as e:
                logger.error(f"Failed to show tables: {str(e)}")
                # Try without catalog specification
                cursor.execute(f"SHOW TABLES IN {DATABRICKS_SCHEMA}")
                tables = cursor.fetchall()
            
            schema_dict = {}
            
            # For each table, get columns
            for table_row in tables:
                table_name = table_row[1]  # Second column is table name
                
                try:
                    full_table_name = f"{DATABRICKS_CATALOG}.{DATABRICKS_SCHEMA}.{table_name}"
                    cursor.execute(f"DESCRIBE TABLE {full_table_name}")
                    column_rows = cursor.fetchall()
                    
                    # Get only column names (first element of each row)
                    column_names = []
                    for row in column_rows:
                        if row[0] and not row[0].startswith("#"):
                            column_names.append(row[0])
                    
                    schema_dict[table_name.lower()] = column_names
                    logger.debug(f"Loaded {len(column_names)} columns for table {table_name}")
                
                except Exception as e:
                    logger.error(f"Failed to describe table {table_name}: {str(e)}")
                    continue
            
            # Save to cache
            if schema_dict:
                with open(SCHEMA_FILE, "w") as f:
                    json.dump(schema_dict, f, indent=2)
                logger.info(f"Schema successfully cached with {len(schema_dict)} tables")
            
            return schema_dict
    
    except Exception as e:
        logger.error(f"Failed to fetch schema from Databricks: {str(e)}")
        return {}

def load_hardcoded_schema() -> dict:
    """Load hardcoded schema as fallback"""
    logger.info("Loading hardcoded schema as fallback")
    
    # Use the schema from the databricks_schema.json document provided
    hardcoded_schema = {
        "entity_pnl_detail": [
            "source_system", "scenario_name", "deal_num", "tran_num", "comm_opt_exercised_flag",
            "broker_fee_type", "strike", "deal_leg", "deal_leg_1", "profile_seq_num", "fee_name",
            "cashflow_type", "pnl_start_date", "pnl_end_date", "payment_date", "rate_dtmn_date",
            "currency", "currency_id", "settlement_type", "volume", "price", "pymt", "df",
            "rate_status", "ltd_realized_value", "ltd_unrealized_value", "ltd_base_realized_value",
            "ltd_base_unrealized_value", "ytd_realized_value", "ytd_unrealized_value",
            "ytd_base_realized_value", "ytd_base_unrealized_value", "mtd_realized_value",
            "mtd_unrealized_value", "mtd_base_realized_value", "mtd_base_unrealized_value",
            "dtd_realized_value", "dtd_unrealized_value", "dtd_base_realized_value",
            "dtd_base_unrealized_value", "base_pymt", "cashflow_status", "ins_seq_num",
            "pnl_methodology", "price_band_seq_num", "portfolio", "portfolio_id",
            "exercised_volume", "price_band_name", "core_ltd_unrealized_value",
            "core_ltd_base_unrealized_value", "fee_user_id", "fee_user_name",
            "fx_fwd_index_to_euro", "parcel_strategy", "parcel_strategy_id",
            "mtd_realized_value_eur", "mtd_unrealized_value_eur", "ytd_realized_value_eur",
            "ytd_unrealized_value_eur", "qtd_realized_value_eur", "qtd_unrealized_value_eur",
            "qtd_realized_value", "qtd_unrealized_value", "qtd_base_realized_value",
            "qtd_base_unrealized_value", "core_ltd_realized_value", "eod_date", "reval_type"
        ],
        "entity_trade_header": [
            "source_system", "deal_num", "tran_num", "version_id", "ins_num", "etrm_template",
            "reference", "toolset_id", "toolset", "ins_type", "ins_type_id", "ins_sub_type_id",
            "ins_sub_type", "internal_lentity", "internal_lentity_id", "internal_bu",
            "internal_bu_id", "buy_sell", "internal_portfolio", "internal_portfolio_id",
            "external_lentity", "external_lentity_id", "external_bu", "external_bu_id",
            "counterparty", "external_bu_is_external", "trader", "trader_id", "input_datetime",
            "trade_start_date", "trade_end_date", "trade_status", "execution_broker",
            "execution_broker_id", "execution_broker_lentity", "execution_broker_lentity_id",
            "external_portfolio", "external_portfolio_id", "last_update_time",
            "last_update_datetime", "trade_price", "trade_currency", "trade_currency_id",
            "payment_currency", "contractual_volume", "contractual_volume_uom",
            "contractual_volume_uom_id", "internal_strategy", "internal_strategy_id",
            "external_strategy", "external_strategy_id", "contract_code", "contract_size",
            "ticker", "first_delivery_date", "last_delivery_date", "strike_price", "premium",
            "call_put", "option_type", "strategy_link_id", "internal_bunit_parent",
            "internal_bunit_parent_id", "portfolio_tranche_1", "portfolio_tranche_2",
            "portfolio_tranche_3", "ext_portfolio_tranche_1", "ext_portfolio_tranche_2",
            "ext_portfolio_tranche_3", "exchange_bu", "exchange_bu_id", "exchange_le",
            "exchange_le_id", "execution_broker_int_or_ext", "exchange_or_otc", "premium_date",
            "option_status", "mig_deal_id", "execution_datetime", "execution_timestamp",
            "spread_trade", "execution_method", "nomination_status", "trading_period",
            "internal_acc_book", "internal_acc_book_id", "external_acc_book",
            "external_acc_book_id", "cascaded_or_exercised", "parent_deal_num", "sleeve_trade",
            "credit_term", "cargo_strategy", "internal_reg_account", "external_reg_account",
            "power_product", "power_product_id", "pre_deal_credit_check_ref_num", "deal_term",
            "offset_tran_num", "order_id", "cleared", "trading_venue", "internal_contact",
            "eeotc", "lots", "trade_date", "relative_trading_period", "exchange_trade_id",
            "sap_book", "deal_pricing_type", "deal_settlement_type", "expiry_date",
            "portfolio_order_id", "cost_center_id", "cost_center_desc", "profit_center_id",
            "profit_center_desc", "carbon_neutral", "option_lead_days", "hedge_spec",
            "non_mtf", "last_update_fo", "exchange_instrument", "trade_source", "eu_noneu",
            "transaction_type", "offset_trade_num", "external_bu_region", "from_cascaded",
            "mo_3", "external_bu_acer", "house_action", "is_basis", "voice_deal", "eod_date",
            "reval_type"
        ],
        "entity_trade_leg": [
            "source_system", "deal_num", "tran_num", "version_id", "deal_leg", "proj_curve",
            "proj_curve_id", "fixing_curve", "fixing_curve_id", "currency", "currency_id",
            "volume_unit", "volume_unit_id", "commodity", "commodity_id", "commodity_sub_group",
            "commodity_sub_group_id", "pay_receive", "idx_currency", "idx_currency_id",
            "idx_volume_unit", "idx_volume_unit_id", "fixed_float", "price_volume_unit",
            "price_volume_unit_id", "settlement_type", "ref_source", "idx_density_adj",
            "deal_formula", "price_spread", "location", "endur_location_id", "payment_term",
            "pair_number", "loc_sub_commodity", "loc_sub_commodity_id", "internal_portfolio",
            "internal_portfolio_id", "index_percentage", "quantity_type", "incoterm", "zone",
            "zone_id", "lifting_period", "lifting_per_period", "proj_method", "pricing_event",
            "title_transfer_location", "title_transfer_location_id", "primary_pymt_event_type",
            "secondary_pymt_event_type", "pymt_date_offset", "pricing_event_type", "tank",
            "tank_id", "ttl_loc_sub_comm", "ttl_loc_sub_comm_id", "ttl_loc_zone",
            "ttl_loc_zone_id", "load_port", "discharge_port", "price_formula", "credit_terms",
            "pricing_period_start", "pricing_period_end", "reset_shift", "rfi_shift",
            "reset_convention", "roll_convention", "ltd_offset", "nearby", "reset_period",
            "avg_period", "commodity_base", "commodity_details", "eod_date", "reval_type"
        ],
        "entity_trade_profile": [
            "source_system", "deal_num", "tran_num", "version_id", "deal_leg",
            "internal_portfolio", "internal_portfolio_id", "profile_id", "profile_start_date",
            "profile_end_date", "payment_date", "notional_volume", "trade_expiry_date",
            "eod_date", "reval_type"
        ]
    }
    
    try:
        # Save hardcoded schema to cache for future use
        with open(SCHEMA_FILE, "w") as f:
            json.dump(hardcoded_schema, f, indent=2)
        logger.info("Hardcoded schema saved to cache")
    except Exception as e:
        logger.warning(f"Could not save hardcoded schema to cache: {str(e)}")
    
    return hardcoded_schema

def get_table_columns(table_name: str) -> list:
    """Get columns for a specific table"""
    schema = load_schema()
    table_key = table_name.lower()
    return schema.get(table_key, [])

def list_tables() -> list:
    """List all available tables"""
    schema = load_schema()
    return list(schema.keys())

def validate_schema() -> bool:
    """Validate that schema is loaded and contains expected tables"""
    schema = load_schema()
    
    if not schema:
        logger.warning("No schema data available")
        return False
    
    expected_tables = ["entity_trade_header", "entity_pnl_detail", "entity_trade_leg", "entity_trade_profile"]
    missing_tables = []
    
    for table in expected_tables:
        if table not in schema:
            missing_tables.append(table)
    
    if missing_tables:
        logger.warning(f"Schema is missing expected tables: {missing_tables}")
        return False
    
    logger.info(f"Schema validation passed - {len(schema)} tables available")
    return True