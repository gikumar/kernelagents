# backend/app/function_calling_manager.py
import logging
import re
import json
import time
import asyncio
from pathlib import Path
from typing import Dict, Optional, List, Any
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FunctionCallingManager:
    """
    Function calling manager compatible with Semantic Kernel 1.35.0
    """
    
    def __init__(self, kernel: Kernel):
        self.kernel = kernel
        self.functions_registered = False
        self._schema_cache = None
        self._schema_last_loaded = None
        self._max_retry_attempts = 3
        self.conversations: Dict[str, Dict] = {}  # Simple conversation storage
        logger.info("✅ Function Calling Manager initialized for SK 1.35.0")

    def _get_conversation_context(self, conversation_id: str) -> Dict:
        """Get or create conversation context"""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = {
                "messages": [],
                "created_at": time.time(),
                "pending_clarification": None
            }
        return self.conversations[conversation_id]
    

    def _get_table_schema(self) -> dict:
        """Get the actual table schema with caching"""
        # Fixed the condition - removed extra parenthesis
        if (self._schema_cache and self._schema_last_loaded and 
            (time.time() - self._schema_last_loaded < 300)):  # 5 minute cache
            return self._schema_cache
        
        try:
            schema_file = Path(__file__).parent / "cache" / "databricks_schema.json"
            if schema_file.exists():
                with open(schema_file, 'r') as f:
                    self._schema_cache = json.load(f)
                    self._schema_last_loaded = time.time()
                    logger.info(f"✅ Loaded schema with {len(self._schema_cache)} tables from cache")
                    return self._schema_cache
            else:
                logger.warning("❌ Schema file not found, using fallback schema")
                return {
                    "entity_trade_header": ["trade_id", "trade_date", "entity", "amount", "status"],
                    "entity_pnl_detail": ["pnl_id", "trade_id", "realized_value", "unrealized_value"],
                    "entity_trade_leg": ["leg_id", "trade_id", "quantity", "price"],
                    "entity_trade_profile": ["profile_id", "trade_id", "profile_name", "profile_value"]
                }
        except Exception as e:
            logger.error(f"❌ Error loading schema: {str(e)}")
            return {}
    
    def _find_column_in_schema(self, column_name: str) -> str:
        """Find which table contains a specific column"""
        schema = self._get_table_schema()
        column_name_lower = column_name.lower()
        
        for table, columns in schema.items():
            for column in columns:
                # Simple matching
                col_lower = column.lower()
                if (column_name_lower in col_lower or 
                    col_lower in column_name_lower or
                    column_name_lower.replace('_', '') == col_lower.replace('_', '') or
                    column_name_lower.replace(' ', '_') == col_lower):
                    return table
        return None

    def _validate_sql_query(self, sql_query: str) -> bool:
        """Validate SQL query for safety"""
        sql_lower = sql_query.lower().strip()
        
        # Prevent destructive operations
        destructive_keywords = ["drop", "delete", "update", "insert", "alter", "truncate", 
                              "create", "modify", "grant", "revoke"]
        if any(keyword in sql_lower for keyword in destructive_keywords):
            return False
        
        # Ensure it's a SELECT query for safety (allow with for CTEs)
        if not (sql_lower.startswith('select') or sql_lower.startswith('with')):
            return False
        
        return True

    def _generate_intelligent_sql(self, prompt: str) -> str:
        """Generate SQL using actual schema knowledge"""
        schema = self._get_table_schema()
        prompt_lower = prompt.lower()
        
        # Default to trade header for general queries
        target_table = "entity_trade_header"
        limit = 20
        
        # Determine target table based on prompt content
        if any(word in prompt_lower for word in ["pnl", "profit", "loss", "realized", "unrealized"]):
            target_table = "entity_pnl_detail"
        elif any(word in prompt_lower for word in ["leg", "quantity", "price"]):
            target_table = "entity_trade_leg"
        elif any(word in prompt_lower for word in ["profile", "characteristic"]):
            target_table = "entity_trade_profile"
        
        # Check for specific column mentions
        for column_pattern in ["ltd_realized_value", "trade_amount", "trader", "portfolio"]:
            if column_pattern in prompt_lower:
                found_table = self._find_column_in_schema(column_pattern)
                if found_table:
                    target_table = found_table
                    break
        
        # Verify the target table exists in schema
        if target_table not in schema:
            logger.warning(f"❌ Target table {target_table} not found in schema, using entity_trade_header")
            target_table = "entity_trade_header"
        
        # Build basic SELECT query
        base_query = f"SELECT * FROM trade_catalog.trade_schema.{target_table}"
        
        # Add WHERE clauses based on prompt
        where_clauses = []
        
        if "recent" in prompt_lower or "latest" in prompt_lower:
            where_clauses.append("trade_date >= CURRENT_DATE - INTERVAL '30' DAY")
        
        if "completed" in prompt_lower:
            where_clauses.append("status = 'completed'")
        elif "pending" in prompt_lower:
            where_clauses.append("status = 'pending'")
        
        # Add WHERE clause if we have conditions
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)
        
        # Handle aggregations
        if any(word in prompt_lower for word in ["count", "how many"]):
            base_query = base_query.replace("SELECT *", "SELECT COUNT(*) as count")
            limit = ""  # Remove limit for counts
        elif any(word in prompt_lower for word in ["sum", "total", "amount"]):
            if "ltd_realized_value" in prompt_lower and target_table == "entity_pnl_detail":
                base_query = base_query.replace("SELECT *", "SELECT SUM(ltd_realized_value) as total_realized_value")
            else:
                base_query = base_query.replace("SELECT *", "SELECT SUM(trade_amount) as total_amount")
            limit = ""  # Remove limit for sums
        
        # Add ORDER BY for specific requests
        if "top" in prompt_lower or "highest" in prompt_lower:
            if target_table == "entity_pnl_detail":
                base_query += " ORDER BY ltd_realized_value DESC"
            else:
                base_query += " ORDER BY trade_amount DESC"
        
        # Add LIMIT
        if limit:
            base_query += f" LIMIT {limit}"
        
        logger.info(f"🤖 Generated SQL: {base_query}")
        return base_query

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

    @kernel_function(name="generate_sql_from_prompt", description="Generate SQL query from natural language description using actual schema knowledge")
    def generate_sql_from_prompt(self, prompt: str) -> str:
        """Generate SQL from natural language using actual schema"""
        try:
            logger.info(f"🤖 Generating intelligent SQL for: {prompt[:100]}...")
            return self._generate_intelligent_sql(prompt)
        except Exception as e:
            error_msg = f"❌ Error generating SQL: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @kernel_function(name="generate_and_execute_sql", description="Generate SQL query from natural language and execute it on Databricks using actual schema")
    def generate_and_execute_sql(self, prompt: str, limit: int = 100) -> str:
        """Generate SQL from natural language and execute it using actual schema"""
        try:
            # Generate SQL using schema knowledge
            sql_query = self._generate_intelligent_sql(prompt)
            
            logger.info(f"📋 Generated schema-aware SQL: {sql_query}")
            
            # Execute the generated query
            logger.info(f"🚀 Executing schema-aware SQL: {sql_query[:200]}...")
            return self.execute_sql_query(sql_query, limit)
            
        except Exception as e:
            error_msg = f"❌ Error in generate_and_execute_sql: {str(e)}"
            logger.error(error_msg)
            return error_msg

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
        """Execute SQL query on Databricks with schema validation"""
        try:
            logger.info(f"📋 Executing SQL query: {sql_query[:100]}...")
            
            # Validate SQL query for safety
            if not self._validate_sql_query(sql_query):
                return "❌ For safety, only SELECT queries are allowed. Destructive operations are blocked."
            
            # Try to execute real query on Databricks
            connection = self._get_databricks_connection()
            if connection is None:
                # Fall back to simulated execution
                return self._simulate_sql_execution(sql_query)
            
            try:
                with connection.cursor() as cursor:
                    # Add LIMIT if not present (for safety) and it's a SELECT
                    sql_lower = sql_query.lower()
                    if "select" in sql_lower and "limit" not in sql_lower:
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
                    
                    result += f"\n✅ REAL execution on Databricks using actual schema"
                    return result
                    
            except Exception as e:
                # Check if it's a column resolution error that should trigger clarification
                error_msg = str(e)
                if "UNRESOLVED_COLUMN" in error_msg or "cannot be resolved" in error_msg:
                    # For direct SQL execution, just return the error
                    return f"❌ SQL execution failed: {error_msg}"
                else:
                    return f"❌ SQL execution failed: {error_msg}"
                    
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
        self.kernel.add_function(
            plugin_name="databricks", 
            function_name="generate_sql_from_prompt", 
            function=self.generate_sql_from_prompt
        )
        self.kernel.add_function(
            plugin_name="databricks", 
            function_name="generate_and_execute_sql", 
            function=self.generate_and_execute_sql
        )
        
        self.functions_registered = True
        logger.info("✅ All functions registered")

    def _direct_function_call(self, prompt: str) -> str:
        """Directly call functions based on prompt content"""
        prompt_lower = prompt.lower()
        
        # Extract limit from prompt
        limit = self._extract_limit_from_prompt(prompt_lower)
        
        if any(keyword in prompt_lower for keyword in ["entity_trade_header", "trade header", "get data", "show data"]):
            return self.get_entity_trade_header_data(limit)  # ✅ Use extracted limit
        
        elif any(keyword in prompt_lower for keyword in ["sql", "query", "select", "execute"]):
            if "select" in prompt_lower:
                sql_match = re.search(r"(select.*?)(?:from|where|limit|group by|order by|$)", prompt_lower, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    sql_query = sql_match.group(1).strip()
                    return self.execute_sql_query(sql_query)
            
            return self.execute_sql_query("SELECT * FROM entity_trade_header LIMIT 10")
        
        else:
            # Use the new schema-aware function for natural language
            return self.generate_and_execute_sql(prompt)

    async def execute_with_function_calling(self, prompt: str, conversation_id: str = "default") -> str:
        """Execute function calling with conversation support"""
        if not self.functions_registered:
            self.register_functions()
        
        # Get conversation context
        context = self._get_conversation_context(conversation_id)
        context["messages"].append({"role": "user", "content": prompt, "timestamp": time.time()})
        
        try:
            # Check for pending clarification first
            if context.get("pending_clarification"):
                result = self._handle_clarification_response(prompt, context)
            else:
                # Use direct function calling (more reliable in SK 1.35.0)
                result = self._direct_function_call_with_context(prompt, context)
            
            context["messages"].append({"role": "assistant", "content": result, "timestamp": time.time()})
            
            return result
            
        except Exception as e:
            error_msg = f"❌ Error in function calling: {str(e)}"
            logger.error(error_msg)
            context["messages"].append({"role": "assistant", "content": error_msg, "timestamp": time.time()})
            return error_msg

    def _direct_function_call_with_context(self, prompt: str, context: Dict) -> str:
        """Direct function calling with conversation context"""
        prompt_lower = prompt.lower()
        
        # Check conversation history for context
        previous_messages = context["messages"][-5:]  # Last 5 messages for context
        
        # Extract limit from prompt (e.g., "get me 1 record", "show 5 records")
        limit = self._extract_limit_from_prompt(prompt_lower)
        
        # Handle natural language queries with schema awareness
        if any(word in prompt_lower for word in ["pnl", "profit", "loss", "realized", "unrealized"]):
            return self.generate_and_execute_sql(prompt)
        
        elif any(word in prompt_lower for word in ["sql", "query", "select", "execute"]):
            if "select" in prompt_lower:
                # Extract SQL from prompt
                sql_match = re.search(r"(select.*?)(?:from|where|limit|group by|order by|$)", prompt_lower, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    sql_query = sql_match.group(1).strip()
                    return self.execute_sql_query(sql_query)
            return self.execute_sql_query("SELECT * FROM entity_trade_header LIMIT 10")
        
        elif any(word in prompt_lower for word in ["data", "show", "get", "list"]):
            return self.get_entity_trade_header_data(limit)  # ✅ Use extracted limit
        
        else:
            # Default to schema-aware SQL generation
            return self.generate_and_execute_sql(prompt)

    def _extract_limit_from_prompt(self, prompt_lower: str) -> int:
        """Extract limit number from prompt text, handling both digits and words"""
        # First try to extract numeric values
        patterns = [
            r'(\d+)\s+record',      # "1 record", "5 records"
            r'(\d+)\s+row',         # "1 row", "5 rows"  
            r'(\d+)\s+entry',       # "1 entry", "5 entries"
            r'show\s+me\s+(\d+)',   # "show me 5"
            r'get\s+me\s+(\d+)',    # "get me 5"
            r'first\s+(\d+)',       # "first 5"
            r'top\s+(\d+)',         # "top 5"
            r'limit\s+(\d+)',       # "limit 5"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        # If no numeric match found, try to parse word numbers
        word_to_number = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'a': 1, 'an': 1, 'single': 1
        }
        
        word_patterns = [
            r'(one|two|three|four|five|six|seven|eight|nine|ten|a|an|single)\s+record',
            r'get\s+me\s+(one|two|three|four|five|six|seven|eight|nine|ten|a|an|single)',
            r'show\s+me\s+(one|two|three|four|five|six|seven|eight|nine|ten|a|an|single)',
        ]
        
        for pattern in word_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                word = match.group(1)
                return word_to_number.get(word, 10)  # Default to 10 if word not found
        
        # Default to 5 if no limit specified
        return 5

    def _handle_clarification_response(self, user_response: str, context: Dict) -> str:
        """Handle user's clarification response"""
        clarification = context.get("pending_clarification")
        if not clarification:
            return "I'm not sure what you're referring to. Could you please ask your question again?"
        
        # Extract column names or other clarifications
        column_names = self._extract_column_names(user_response)
        
        if column_names:
            # Retry with clarified information
            original_prompt = clarification.get("original_prompt", "")
            improved_sql = self._generate_intelligent_sql_with_columns(original_prompt, column_names)
            
            try:
                result = self._execute_sql_query_direct(improved_sql)
                context["pending_clarification"] = None  # Clear clarification
                return result
            except Exception as e:
                return f"❌ Still couldn't execute the query: {str(e)}\n\nPlease try being more specific."
        
        # If no useful information extracted, ask again
        return "I still need help understanding. Could you specify which exact columns you're looking for? Example: 'Use profit_date and realized_pnl columns'"    

    def _generate_intelligent_sql_with_columns(self, prompt: str, column_names: List[str]) -> str:
        """Generate SQL using specific column names"""
        # Your existing _generate_intelligent_sql logic, but using provided columns
        # This would be enhanced to use the specified columns
        base_sql = self._generate_intelligent_sql(prompt)
        
        # For now, return the base SQL - you could enhance this to use specific columns
        return base_sql
    

    def _handle_column_resolution_error(self, error_msg: str, prompt: str, context: Dict) -> str:
        """Handle column resolution errors by asking for clarification"""
        # Extract suggested columns from error message
        suggestions = []
        if "Did you mean one of the following?" in error_msg:
            import re
            match = re.search(r'\[(.*?)\]', error_msg)
            if match:
                suggestions = match.group(1).replace('`', '').split(', ')
        
        # Store clarification context
        context["pending_clarification"] = {
            "original_prompt": prompt,
            "error": error_msg,
            "suggestions": suggestions,
            "timestamp": time.time()
        }
        
        response = "🤖 I need help understanding your query:\n\n"
        response += f"**Original question**: {prompt}\n\n"
        response += "**Issue**: I couldn't find some columns you mentioned.\n\n"
        
        if suggestions:
            response += "**Available similar columns**:\n"
            for suggestion in suggestions:
                response += f"• {suggestion}\n"
            response += "\n"
        
        response += "**Please clarify**:\n"
        response += "- Which specific columns should I use?\n"
        response += "- Example: 'Use the profit_date column instead'\n\n"
        response += "Or rephrase your question with different column names."
        
        return response

    def _extract_column_names(self, text: str) -> List[str]:
        """Extract column names from user response"""
        # Simple pattern matching for column names
        patterns = [
            r'use (?:the )?([a-zA-Z_][a-zA-Z0-9_]*)',
            r'columns? ([a-zA-Z_][a-zA-Z0-9_]*(?:,\s*[a-zA-Z_][a-zA-Z0-9_]*)*)',
            r'([a-zA-Z_][a-zA-Z0-9_]*)(?: and |, |\s+)([a-zA-Z_][a-zA-Z0-9_]*)'
        ]
        
        columns = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    columns.extend([col.strip() for col in match if col.strip()])
                else:
                    columns.append(match.strip())
        
        return list(set(columns))

    def _execute_sql_query_direct(self, sql_query: str) -> str:
        """Direct SQL execution without retry logic (used in clarification handling)"""
        connection = self._get_databricks_connection()
        if connection is None:
            return self._simulate_sql_execution(sql_query)
        
        try:
            with connection.cursor() as cursor:
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
                    for i, row in enumerate(data[:3]):
                        result += f"{i+1}. {row}\n"
                
                result += f"\n✅ REAL execution on Databricks using actual schema"
                return result
                
        except Exception as e:
            raise e  # Re-raise for the clarification handler
        finally:
            connection.close()


# Available functions
AVAILABLE_FUNCTIONS = [
    "get_entity_trade_header_data",
    "execute_sql_query",
    "generate_sql_from_prompt",
    "generate_and_execute_sql"
]