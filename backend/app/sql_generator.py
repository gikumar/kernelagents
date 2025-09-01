# backend/app/sql_generator.py
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SQLGenerator:
    """Natural Language to SQL generator using LLM with schema awareness"""
    
    def __init__(self):
        self.schema_data = self._load_schema()
        self.schema_context = self._build_schema_context()
        logger.info(f"SQL Generator initialized with {len(self.schema_data)} tables")
        
    def _load_schema(self) -> Dict:
        """Load schema from cache file"""
        schema_file = Path(__file__).parent / "cache" / "databricks_schema.json"
        try:
            if schema_file.exists():
                with open(schema_file, "r") as f:
                    schema_data = json.load(f)
                    logger.info(f"Loaded schema with {len(schema_data)} tables")
                    return schema_data
            else:
                logger.warning("Schema cache file not found, attempting to load from schema_utils")
                # Try to use schema_utils as fallback
                try:
                    from schema_utils import load_schema
                    return load_schema()
                except ImportError:
                    logger.error("Could not import schema_utils")
                    return {}
        except Exception as e:
            logger.error(f"Error loading schema: {str(e)}")
            return {}
    
    def _build_schema_context(self) -> str:
        """Build comprehensive schema context for LLM prompts"""
        if not self.schema_data:
            return "No schema information available."
        
        context = "Database Schema Information:\n\n"
        
        for table_name, columns in self.schema_data.items():
            context += f"Table: {table_name}\n"
            context += f"Columns: {', '.join(columns)}\n\n"
        
        # Add common query patterns and examples
        context += """
Common Query Patterns:
- Use LIMIT for restricting results: SELECT * FROM table LIMIT 10
- Filter with WHERE: SELECT * FROM table WHERE column = 'value'
- Sort with ORDER BY: SELECT * FROM table ORDER BY date_column DESC
- Aggregate with GROUP BY: SELECT category, SUM(amount) FROM table GROUP BY category
- Join tables when needed: SELECT t1.*, t2.column FROM table1 t1 JOIN table2 t2 ON t1.id = t2.id

Important Notes:
- Always use fully qualified table names with catalog and schema
- Use proper quoting for column names with spaces or special characters
- Include appropriate filters to avoid returning too much data
- Use appropriate date filters for time-based queries
"""
        return context
    
    def _extract_limit_from_query(self, natural_language_query: str) -> int:
        """Extract limit from natural language query"""
        query_lower = natural_language_query.lower()
        
        # Pattern matching for numbers
        patterns = [
            r"(\d+)\s+(records?|rows?|results?)",
            r"top\s+(\d+)",
            r"first\s+(\d+)",
            r"show\s+me\s+(\d+)",
            r"get\s+(\d+)",
            r"limit\s+to\s+(\d+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        # Default limit based on query context
        if any(word in query_lower for word in ["summary", "overview", "total", "count"]):
            return 100
        elif any(word in query_lower for word in ["recent", "latest", "newest"]):
            return 20
        else:
            return 10
    
    def _validate_sql_safety(self, sql_query: str) -> bool:
        """Validate SQL query for safety"""
        sql_lower = sql_query.lower().strip()
        
        # Block destructive operations
        destructive_keywords = [
            "drop", "delete", "update", "insert", "alter", "truncate", 
            "create", "modify", "grant", "revoke", "exec", "execute",
            "merge", "replace", "commit", "rollback"
        ]
        
        if any(keyword in sql_lower for keyword in destructive_keywords):
            return False
        
        # Only allow SELECT queries
        if not (sql_lower.startswith('select') or sql_lower.startswith('with')):
            return False
        
        # Check for potential injection patterns
        injection_patterns = [
            r";\s*--", r";\s*#", r";\s*\/\*", r"union.*select",
            r"exec\s*\(?", r"xp_", r"sp_", r"waitfor.*delay"
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sql_lower, re.IGNORECASE):
                return False
        
        return True
    
    # In sql_generator.py, update the _post_process_sql method:

    def _post_process_sql(self, sql_query: str, natural_language_query: str) -> str:
        """Post-process SQL to ensure quality and safety - NUCLEAR OPTION"""
        try:
            # Use the correct catalog and schema names
            correct_prefix = "trade_catalog.trade_schema."
            
            # NUCLEAR OPTION: Remove ANY pattern that creates a table reference with more than 2 dots
            # This will catch all the weird patterns the LLM might generate
            import re
            
            # Find all table references in the SQL
            table_pattern = r'\b(?:[a-zA-Z_][a-zA-Z0-9_]*\.){2,}[a-zA-Z_][a-zA-Z0-9_]*\b'
            table_matches = re.findall(table_pattern, sql_query)
            
            for bad_table_ref in table_matches:
                # Extract just the table name (the last part after the last dot)
                table_name = bad_table_ref.split('.')[-1]
                
                # Replace with correct format
                correct_ref = f"{correct_prefix}{table_name}"
                sql_query = sql_query.replace(bad_table_ref, correct_ref)
            
            # Also handle simple table names without qualification
            for table_name in self.schema_data.keys():
                # Pattern for unqualified table names
                simple_pattern = rf'\b{table_name}\b'
                if re.search(simple_pattern, sql_query) and f"{correct_prefix}{table_name}" not in sql_query:
                    correct_ref = f"{correct_prefix}{table_name}"
                    sql_query = re.sub(simple_pattern, correct_ref, sql_query)
            
            # Ensure LIMIT is present
            if "limit" not in sql_query.lower():
                limit = self._extract_limit_from_query(natural_language_query)
                sql_query += f" LIMIT {limit}"
        
        except Exception as e:
            logger.debug(f"Post-processing note: {str(e)}")
        
        return sql_query
    
    
    async def generate_sql_from_natural_language(self, natural_language_query: str, kernel) -> str:
        """Generate SQL from natural language using LLM"""
        try:
            from semantic_kernel.contents import ChatHistory
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
            
            # Build the prompt with schema context
            # In the prompt, be more specific about the format:
            # Update the prompt to be more specific:
            prompt = f"""
            Database Schema Context:
            {self.schema_context}

            User Request: {natural_language_query}

            CRITICAL INSTRUCTIONS:
            1. Generate a clean, efficient SQL SELECT query that answers the user's request
            2. Use fully qualified table names in EXACTLY this format: trade_catalog.trade_schema.table_name
            3. DO NOT use catalog.schema.table_name format
            4. DO NOT duplicate catalog or schema names
            5. Include appropriate filters to avoid returning excessive data
            6. Use LIMIT to restrict results to a reasonable number (10-100 rows typically)
            7. Ensure the query is syntactically correct for Databricks SQL
            8. Only return the SQL query, no explanations or additional text

            Example of CORRECT format: 
            SELECT * FROM trade_catalog.trade_schema.entity_trade_header LIMIT 10

            Example of INCORRECT format:
            SELECT * FROM catalog.schema.trade_catalog.trade_schema.entity_trade_header

            SQL Query:
            """
            
            # Create chat history
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a SQL expert that converts natural language to efficient SQL queries.")
            chat_history.add_user_message(prompt)
            
            # Get the chat service with improved error handling
            chat_service = self._get_chat_service_from_kernel(kernel)
            if not chat_service:
                raise ValueError("Azure OpenAI chat service not available in kernel")
            
            # Generate SQL
            settings = OpenAIChatPromptExecutionSettings(
                service_id=getattr(chat_service, "service_id", "azure_gpt4o"),
                max_tokens=1000,
                temperature=0.1  # Low temperature for consistent SQL generation
            )
            
            result = await chat_service.get_chat_message_contents(
                chat_history=chat_history,
                settings=settings
            )
            
            if not result or len(result) == 0:
                raise ValueError("No response from LLM")
            
            raw_sql = result[0].content.strip()
            
            # Clean up the SQL (remove markdown code blocks if present)
            raw_sql = self._clean_sql_response(raw_sql)
            
            # Validate safety
            if not self._validate_sql_safety(raw_sql):
                raise ValueError("Generated SQL query failed safety validation")
            
            # Post-process for quality
            final_sql = self._post_process_sql(raw_sql, natural_language_query)
            
            logger.info(f"Generated SQL: {final_sql}")
            return final_sql
            
        except Exception as e:
            logger.error(f"Error generating SQL: {str(e)}")
            raise
    
    def _get_chat_service_from_kernel(self, kernel):
        """Get chat service from kernel with multiple fallback strategies"""
        chat_service = None
        
        # Strategy 1: Get by service ID
        try:
            chat_service = kernel.get_service("azure_gpt4o")
            if chat_service:
                logger.info("Retrieved chat service by service_id 'azure_gpt4o'")
                return chat_service
        except Exception as e:
            logger.debug(f"Failed to get service by ID: {str(e)}")
        
        # Strategy 2: Get AzureChatCompletion service
        try:
            from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
            services = kernel.get_services(type=AzureChatCompletion)
            if services:
                chat_service = next(iter(services.values()))
                logger.info("Retrieved AzureChatCompletion service")
                return chat_service
        except Exception as e:
            logger.debug(f"Failed to get AzureChatCompletion service: {str(e)}")
        
        # Strategy 3: Get any service with chat capabilities
        try:
            all_services = kernel.get_services()
            for service_id, service in all_services.items():
                if hasattr(service, 'get_chat_message_contents'):
                    logger.info(f"Retrieved chat service by capability check: {service_id}")
                    return service
        except Exception as e:
            logger.debug(f"Failed to get service by capability: {str(e)}")
        
        return None
    
    def _clean_sql_response(self, raw_sql: str) -> str:
        """Clean SQL response from LLM"""
        # Remove markdown code blocks
        if raw_sql.startswith("```sql"):
            raw_sql = re.sub(r"^```sql\s*", "", raw_sql)
        if raw_sql.startswith("```"):
            raw_sql = re.sub(r"^```\s*", "", raw_sql)
        raw_sql = re.sub(r"```\s*$", "", raw_sql).strip()
        
        # Remove any explanatory text that might come before or after the SQL
        lines = raw_sql.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            line = line.strip()
            if line.upper().startswith(('SELECT', 'WITH')):
                in_sql = True
                sql_lines.append(line)
            elif in_sql and line:
                # Continue collecting SQL lines
                if any(keyword in line.upper() for keyword in ['FROM', 'WHERE', 'JOIN', 'GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING']):
                    sql_lines.append(line)
                elif line.endswith(';'):
                    sql_lines.append(line.rstrip(';'))
                    break
                elif not line.startswith(('#', '--', '/*')):  # Skip comments
                    sql_lines.append(line)
        
        if sql_lines:
            return ' '.join(sql_lines)
        else:
            return raw_sql
    
    def get_available_tables(self) -> List[str]:
        """Get list of available tables in schema"""
        return list(self.schema_data.keys())
    
    def get_table_columns(self, table_name: str) -> List[str]:
        """Get columns for a specific table"""
        return self.schema_data.get(table_name.lower(), [])
    
    def validate_table_exists(self, table_name: str) -> bool:
        """Check if table exists in schema"""
        return table_name.lower() in self.schema_data
    
    def get_schema_summary(self) -> str:
        """Get a summary of the schema for debugging"""
        if not self.schema_data:
            return "No schema data available"
        
        summary = f"Schema contains {len(self.schema_data)} tables:\n"
        for table_name, columns in self.schema_data.items():
            summary += f"- {table_name}: {len(columns)} columns\n"
        
        return summary