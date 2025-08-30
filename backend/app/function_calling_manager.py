# backend/app/function_calling_manager.py
import logging
import re
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class FunctionCallingManager:
    """
    Direct function calling manager with proper Databricks connection
    """
    
    def __init__(self, kernel: Kernel):
        self.kernel = kernel
        self.functions_registered = False
        logger.info("✅ Function Calling Manager initialized")
    
    def _get_databricks_connection(self):
        """Get Databricks connection with error handling"""
        try:
            from config import (
                DATABRICKS_SERVER_HOSTNAME,
                DATABRICKS_ACCESS_TOKEN,
                DATABRICKS_HTTP_PATH
            )
            
            if not all([DATABRICKS_SERVER_HOSTNAME, DATABRICKS_ACCESS_TOKEN, DATABRICKS_HTTP_PATH]):
                logger.error("❌ Databricks connection parameters not configured")
                return None
            
            # Import inside try block to handle numpy issues
            try:
                import databricks.sql
            except ImportError as e:
                logger.error(f"❌ Databricks SQL connector not installed: {e}")
                return None
            except Exception as e:
                logger.error(f"❌ Error importing databricks.sql: {e}")
                return None
            
            logger.info(f"🔗 Connecting to Databricks: {DATABRICKS_SERVER_HOSTNAME}")
            connection = databricks.sql.connect(
                server_hostname=DATABRICKS_SERVER_HOSTNAME,
                http_path=DATABRICKS_HTTP_PATH,
                access_token=DATABRICKS_ACCESS_TOKEN
            )
            
            logger.info("✅ Connected to Databricks successfully")
            return connection
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Databricks: {str(e)}")
            return None
    
    @kernel_function(name="get_entity_trade_header_data", description="Get data from entity_trade_header table in Databricks")
    def get_entity_trade_header_data(self, limit: int = 20) -> str:
        """Get data from entity_trade_header table"""
        try:
            logger.info(f"📊 Getting data from entity_trade_header (limit: {limit})")
            
            # Try to get real data from Databricks
            connection = self._get_databricks_connection()
            if connection is None:
                # Fall back to simulated data if connection fails
                return self._get_simulated_data(limit)
            
            try:
                with connection.cursor() as cursor:
                    query = f"SELECT * FROM trade_catalog.trade_schema.entity_trade_header LIMIT {limit}"
                    cursor.execute(query)
                    
                    # Get column names
                    columns = [desc[0] for desc in cursor.description]
                    data = []
                    
                    # Fetch results
                    for row in cursor.fetchall():
                        row_dict = {}
                        for idx, col in enumerate(columns):
                            value = row[idx]
                            # Handle different data types
                            if value is None:
                                row_dict[col] = "NULL"
                            elif hasattr(value, 'isoformat'):  # Handle datetime
                                row_dict[col] = value.isoformat()
                            else:
                                row_dict[col] = str(value)
                        data.append(row_dict)
                    
                    # Format the results
                    result = f"📊 entity_trade_header data ({len(data)} rows):\n\n"
                    for item in data:
                        result += "• "
                        for col, value in item.items():
                            result += f"{col}: {value} | "
                        result = result[:-3] + "\n"  # Remove trailing " | "
                    
                    result += f"\n✅ REAL DATA from Databricks - Function executed successfully"
                    return result
                    
            except Exception as e:
                logger.error(f"❌ Query execution error: {str(e)}")
                return f"❌ Query execution failed: {str(e)}"
                
            finally:
                connection.close()
            
        except Exception as e:
            error_msg = f"❌ Error in get_entity_trade_header_data: {str(e)}"
            logger.error(error_msg)
            return self._get_simulated_data(limit)  # Fall back to simulated data

    def _get_simulated_data(self, limit: int = 20) -> str:
        """Fallback simulated data"""
        simulated_data = [
            {"trade_id": 1, "trade_date": "2023-09-15", "entity": "Entity A", "amount": 15000.50, "status": "completed"},
            {"trade_id": 2, "trade_date": "2023-09-16", "entity": "Entity B", "amount": 20000.00, "status": "pending"},
            {"trade_id": 3, "trade_date": "2023-09-17", "entity": "Entity C", "amount": 25000.75, "status": "completed"},
            {"trade_id": 4, "trade_date": "2023-09-18", "entity": "Entity D", "amount": 18000.25, "status": "cancelled"},
            {"trade_id": 5, "trade_date": "2023-09-19", "entity": "Entity E", "amount": 22000.50, "status": "completed"}
        ]
        
        result = f"📊 SIMULATED entity_trade_header data (showing {min(limit, len(simulated_data))} of {len(simulated_data)} rows):\n\n"
        for item in simulated_data[:limit]:
            result += f"• Trade {item['trade_id']}: {item['trade_date']} | {item['entity']} | ${item['amount']:,.2f} | {item['status']}\n"
        
        result += f"\n⚠️  Using simulated data (Databricks connection issue)"
        return result

    @kernel_function(name="execute_sql_query", description="Execute SQL query on Databricks SQL Warehouse")
    def execute_sql_query(self, sql_query: str, limit: int = 100) -> str:
        """Execute SQL query on Databricks"""
        try:
            logger.info(f"📋 Executing SQL query: {sql_query[:100]}...")
            
            # Try to execute real query on Databricks
            connection = self._get_databricks_connection()
            if connection is None:
                # Fall back to simulated execution
                return self._simulate_sql_execution(sql_query)
            
            try:
                with connection.cursor() as cursor:
                    # Add LIMIT if not present (for safety)
                    sql_lower = sql_query.lower()
                    if "limit" not in sql_lower:
                        sql_query += f" LIMIT {limit}"
                    
                    cursor.execute(sql_query)
                    
                    # Get results
                    columns = [desc[0] for desc in cursor.description]
                    data = []
                    for row in cursor.fetchall():
                        row_dict = {}
                        for idx, col in enumerate(columns):
                            value = row[idx]
                            if value is None:
                                row_dict[col] = "NULL"
                            elif hasattr(value, 'isoformat'):
                                row_dict[col] = value.isoformat()
                            else:
                                row_dict[col] = str(value)
                        data.append(row_dict)
                    
                    result = f"✅ SQL Query Execution Result:\n\n"
                    result += f"Executed: {sql_query}\n\n"
                    result += f"Columns: {', '.join(columns)}\n"
                    result += f"Rows returned: {len(data)}\n\n"
                    
                    if data:
                        result += "First few rows:\n"
                        for i, row in enumerate(data[:3]):  # Show first 3 rows
                            result += f"{i+1}. {row}\n"
                    
                    result += f"\n✅ REAL execution on Databricks"
                    return result
                    
            except Exception as e:
                logger.error(f"❌ SQL execution error: {str(e)}")
                return f"❌ SQL execution failed: {str(e)}"
                
            finally:
                connection.close()
            
        except Exception as e:
            error_msg = f"❌ Error in execute_sql_query: {str(e)}"
            logger.error(error_msg)
            return self._simulate_sql_execution(sql_query)

    def _simulate_sql_execution(self, sql_query: str) -> str:
        """Fallback simulated SQL execution"""
        result = f"✅ SQL Query Execution Result:\n\n"
        result += f"Executed: {sql_query}\n\n"
        result += f"Simulated result: Query would connect to Databricks and return actual data\n"
        result += f"Status: Success (simulated)\n"
        result += f"Rows affected: Would return actual row count\n"
        result += f"\n⚠️  Using simulated execution (Databricks connection issue)"
        return result

    def register_functions(self):
        """Register functions with the kernel"""
        logger.info("🔧 Registering functions...")
        
        self.kernel.add_function(
            plugin_name="databricks", 
            function_name="get_entity_trade_header_data", 
            function=self.get_entity_trade_header_data
        )
        self.kernel.add_function(
            plugin_name="databricks", 
            function_name="execute_sql_query", 
            function=self.execute_sql_query
        )
        
        self.functions_registered = True
        logger.info("✅ Functions registered")

    def _direct_function_call(self, prompt: str) -> str:
        """Directly call functions based on prompt content"""
        prompt_lower = prompt.lower()
        
        if any(keyword in prompt_lower for keyword in ["entity_trade_header", "trade header", "get data", "show data"]):
            limit_match = re.search(r"limit\s+(\d+)", prompt_lower)
            limit = int(limit_match.group(1)) if limit_match else 10
            return self.get_entity_trade_header_data(limit)
        
        elif any(keyword in prompt_lower for keyword in ["sql", "query", "select", "execute"]):
            if "select" in prompt_lower:
                sql_match = re.search(r"(select.*?)(?:from|where|limit|group by|order by|$)", prompt_lower, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    sql_query = sql_match.group(1).strip()
                    return self.execute_sql_query(sql_query)
            
            return self.execute_sql_query("SELECT * FROM entity_trade_header LIMIT 10")
        
        else:
            return "🤖 I can help you with:\n• Getting data from entity_trade_header table\n• Executing SQL queries on Databricks\n\nTry: 'get entity_trade_header data' or 'execute SQL query'"

    async def execute_with_function_calling(self, prompt: str, max_tokens: int = 2000):
        """Direct function calling"""
        if not self.functions_registered:
            self.register_functions()
        
        try:
            logger.info(f"🎯 Direct function calling for: {prompt[:100]}...")
            result = self._direct_function_call(prompt)
            return result
            
        except Exception as e:
            error_msg = f"❌ Error in function calling: {str(e)}"
            logger.error(error_msg)
            return error_msg

# Available functions
AVAILABLE_FUNCTIONS = [
    "get_entity_trade_header_data",
    "execute_sql_query"
]