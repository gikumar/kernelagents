# backend/app/function_calling_manager.py
import logging
import re
import json
import time
import os
import asyncio
from pathlib import Path
from typing import Dict, Optional, List, Any
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings

# Set up logger
logger = logging.getLogger(__name__)

class FunctionCallingManager:
    """
    Function calling manager with intelligent routing and NL-to-SQL
    """
    
    def __init__(self, kernel: Kernel):
        logger.info("💥 FunctionCallingManager initializing")
        self.kernel = kernel
        self.functions_registered = False
        self.conversations: Dict[str, Dict] = {}
        self.chat_service = None
        self.sql_generator = None
        
        # Initialize components
        self._initialize_azure_openai()
        self._initialize_sql_generator()
        
        # Register functions
        self.register_functions()
        
        logger.info("💥 Function Calling Manager initialized successfully")

    def _initialize_azure_openai(self):
        """Initialize Azure OpenAI connection"""
        logger.info("💥 Initializing Azure OpenAI connection")
        try:
            from config import (
                AZURE_OPENAI_ENDPOINT, 
                AZURE_OPENAI_KEY, 
                AZURE_OPENAI_DEPLOYMENT, 
                AZURE_OPENAI_API_VERSION
            )
            
            # Check if service already exists
            try:
                existing_service = self.kernel.get_service("azure_gpt4o")
                self.chat_service = existing_service
                logger.info("💥 Azure OpenAI service already exists in kernel, reusing it")
                return
            except ValueError:
                # Service doesn't exist yet, create it
                logger.info("💥 Creating new Azure OpenAI service")
                pass
            
            if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT]):
                raise ValueError("Missing required Azure OpenAI configuration")
            
            # FIX: Import AzureChatCompletion here to avoid circular imports
            from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
            
            self.chat_service = AzureChatCompletion(
                service_id="azure_gpt4o",
                deployment_name=AZURE_OPENAI_DEPLOYMENT,
                endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_KEY,
                api_version=AZURE_OPENAI_API_VERSION
            )
            
            self.kernel.add_service(self.chat_service)
            logger.info("💥 Azure OpenAI GPT-4o initialized successfully")
            
        except Exception as e:
            logger.error(f"💥 Failed to initialize Azure OpenAI: {str(e)}")
            raise

    def _initialize_sql_generator(self):
        """Initialize SQL generator"""
        logger.info("💥 Initializing SQL Generator")
        try:
            from sql_generator import SQLGenerator
            self.sql_generator = SQLGenerator()
            logger.info("💥 SQL Generator initialized successfully")
        except Exception as e:
            logger.error(f"💥 Failed to initialize SQL Generator: {str(e)}")
            raise

    def _get_conversation_context(self, conversation_id: str) -> Dict:
        """Get or create conversation context"""
        logger.info(f"💥 Getting conversation context for ID: {conversation_id}")
        if conversation_id not in self.conversations:
            logger.info(f"💥 Creating new conversation context for ID: {conversation_id}")
            self.conversations[conversation_id] = {
                "messages": [],
                "created_at": time.time(),
                "pending_clarification": None
            }
        return self.conversations[conversation_id]

    def _get_databricks_connection(self):
        """Get Databricks connection with error handling"""
        logger.info("💥 Getting Databricks connection")
        try:
            from config import (
                DATABRICKS_SERVER_HOSTNAME,
                DATABRICKS_ACCESS_TOKEN,
                DATABRICKS_HTTP_PATH
            )
            
            if not all([DATABRICKS_SERVER_HOSTNAME, DATABRICKS_ACCESS_TOKEN, DATABRICKS_HTTP_PATH]):
                logger.error("💥 Databricks connection parameters not configured")
                return None
            
            try:
                import databricks.sql
            except ImportError as e:
                logger.error(f"💥 Databricks SQL connector not installed: {e}")
                return None
            
            logger.info(f"💥 Connecting to Databricks: {DATABRICKS_SERVER_HOSTNAME}")
            connection = databricks.sql.connect(
                server_hostname=DATABRICKS_SERVER_HOSTNAME,
                http_path=DATABRICKS_HTTP_PATH,
                access_token=DATABRICKS_ACCESS_TOKEN
            )
            
            logger.info("💥 Connected to Databricks successfully")
            return connection
            
        except Exception as e:
            logger.error(f"💥 Failed to connect to Databricks: {str(e)}")
            return None

    @kernel_function(
        name="query_trade_data",
        description="Query trade data from database using natural language. Use this when user asks about trades, deals, transactions, or wants to see trade information"
    )
    async def query_trade_data(self, natural_language_query: str = "") -> str:
        """Query trade data using natural language to SQL conversion"""
        logger.info(f"💥 query_trade_data called with query: '{natural_language_query[:50]}...'")
        
        try:
            logger.info(f"💥 Processing natural language query: {natural_language_query}")
            
            if not self.sql_generator:
                logger.error("💥 SQL Generator not available")
                return "SQL Generator not available. Please check configuration."
            
            # Generate SQL from natural language
            logger.info("💥 Generating SQL from natural language")
            sql_query = await self.sql_generator.generate_sql_from_natural_language(
                natural_language_query, self.kernel
            )
            
            logger.info(f"💥 Generated SQL: {sql_query}")
            
            # If SQL generation failed, provide a helpful response
            if "error" in sql_query.lower() or "not available" in sql_query.lower():
                logger.warning(f"💥 SQL generation failed: {sql_query}")
                return f"I couldn't generate a valid SQL query for your request. Please try rephrasing your question. Error: {sql_query}"
            
            # Execute the query and get results
            logger.info("💥 Executing SQL query")
            result_text, raw_data = await self._execute_sql_query(sql_query, natural_language_query)
            
            # Generate visualization if appropriate
            logger.info("💥 Checking if visualization is needed")
            chart_data = await self._generate_visualization_if_needed(natural_language_query, raw_data)
            
            if chart_data:
                logger.info("💥 Visualization generated successfully, returning JSON response")
                # Return JSON with both text response and visualization
                response_data = {
                    "text_response": result_text,
                    "visualization": chart_data,
                    "has_chart": True
                }
                return json.dumps(response_data)
            else:
                logger.info("💥 No visualization needed, returning text response only")
                return result_text
                
        except Exception as e:
            error_msg = f"💥 Error processing query: {str(e)}"
            logger.error(error_msg)
            return f"I encountered an error while processing your request. Please try again or rephrase your question. Error: {str(e)}"

    async def _execute_sql_query(self, sql_query: str, original_query: str = "") -> tuple:
        """Execute SQL query and return both formatted results and raw data"""
        logger.info(f"💥 _execute_sql_query called with SQL: {sql_query[:100]}...")
        
        connection = self._get_databricks_connection()
        if connection is None:
            logger.error("💥 Database connection not available")
            return "Database connection not available. Please check Databricks configuration.", None
        
        try:
            with connection.cursor() as cursor:
                logger.info("💥 Executing SQL cursor")
                cursor.execute(sql_query)
                
                columns = [desc[0] for desc in cursor.description]
                raw_data = []
                formatted_data = []
                
                logger.info(f"💥 Fetching results with {len(columns)} columns: {columns}")
                for row in cursor.fetchall():
                    row_dict = {}
                    formatted_row = {}
                    for idx, col in enumerate(columns):
                        value = row[idx]
                        if value is None:
                            row_dict[col] = "NULL"
                            formatted_row[col] = "NULL"
                        elif hasattr(value, 'isoformat'):
                            row_dict[col] = value.isoformat()
                            formatted_row[col] = value.isoformat()
                        else:
                            row_dict[col] = str(value)
                            formatted_row[col] = str(value)
                    raw_data.append(row_dict)
                    formatted_data.append(formatted_row)
                
                # Format results
                logger.info("💥 Formatting query results")
                result_text = self._format_query_results(formatted_data, columns, sql_query, original_query)
                logger.info(f"💥 Query executed successfully, returned {len(raw_data)} rows")
                return result_text, raw_data
                
        except Exception as e:
            logger.error(f"💥 Query execution error: {str(e)}")
            return f"Query execution failed: {str(e)}", None
            
        finally:
            connection.close()
            logger.info("💥 Database connection closed")

    def _format_query_results(self, data: list, columns: list, sql_query: str, original_query: str) -> str:
        """Format query results intelligently"""
        logger.info(f"💥 _format_query_results called with {len(data)} rows")
        
        if not data:
            logger.info("💥 No data found for query")
            return f"No results found for: '{original_query}'\n\nQuery: {sql_query}"
        
        result = f"Query Results ({len(data)} row{'s' if len(data) != 1 else ''}):\n\n"
        
        # Format based on data size
        if len(data) <= 5 and len(columns) <= 8:
            logger.info("💥 Using detailed table format")
            result += self._format_detailed_table(data, columns)
        else:
            logger.info("💥 Using compact table format")
            result += self._format_compact_table(data, columns)
        
        # Add query context
        result += f"\nGenerated from: '{original_query}'\n"
        result += f"SQL: {sql_query}\n"
        
        logger.info("💥 Query results formatted successfully")
        return result

    def _format_detailed_table(self, data: list, columns: list) -> str:
        """Format data as a detailed table"""
        logger.info("💥 _format_detailed_table called")
        result = ""
        for i, row in enumerate(data, 1):
            result += f"**Row {i}:**\n"
            for col in columns:
                value = row.get(col, "N/A")
                if value and len(str(value)) > 100:
                    value = str(value)[:100] + "..."
                result += f"  • {col}: {value}\n"
            result += "\n"
        logger.info("💥 Detailed table formatted")
        return result

    def _format_compact_table(self, data: list, columns: list) -> str:
        """Format data as a compact table"""
        logger.info("💥 _format_compact_table called")
        # Select key columns for display
        key_columns = self._get_key_columns(columns)
        logger.info(f"💥 Selected key columns: {key_columns}")
        
        # Create header
        headers = ["#"] + key_columns
        header_line = "| " + " | ".join(headers) + " |"
        separator = "|" + "|".join(["---" for _ in headers]) + "|"
        
        result = header_line + "\n" + separator + "\n"
        
        # Add rows
        for i, row in enumerate(data, 1):
            row_values = [str(i)]
            for col in key_columns:
                value = row.get(col, "N/A")
                if value and len(str(value)) > 25:
                    value = str(value)[:22] + "..."
                row_values.append(str(value))
            result += "| " + " | ".join(row_values) + " |\n"
        
        logger.info("💥 Compact table formatted")
        return result

    def _get_key_columns(self, all_columns: list) -> list:
        """Identify key columns to display"""
        logger.info(f"💥 _get_key_columns called with columns: {all_columns}")
        key_columns = []
        priority_columns = [
            'deal_num', 'tran_num', 'trade_date', 'currency', 'amount', 
            'volume', 'price', 'trader', 'buy_sell', 'status'
        ]
        
        # Add priority columns that exist
        for col in priority_columns:
            if col in all_columns:
                key_columns.append(col)
        
        # Fill remaining slots
        if len(key_columns) < 6:
            additional_cols = [col for col in all_columns if col not in key_columns]
            key_columns.extend(additional_cols[:6 - len(key_columns)])
        
        logger.info(f"💥 Final key columns selected: {key_columns}")
        return key_columns

    @kernel_function(
        name="explain_concept",
        description="Explain trading concepts, definitions, or general information"
    )
    async def explain_concept(self, concept: str) -> str:
        """Explain trading concepts using LLM"""
        logger.info(f"💥 explain_concept called with concept: '{concept}'")
        
        try:
            logger.info(f"💥 Explaining concept: {concept}")
            
            if not self.chat_service:
                logger.error("💥 LLM service not available")
                return "LLM service not available. Please check Azure OpenAI configuration."
            
            explanation_prompt = f"""
            Please provide a clear, comprehensive explanation of '{concept}' in the context of trading and finance.
            
            Your explanation should include:
            1. A simple and clear definition
            2. How it works in practical trading scenarios
            3. Why it's important in financial markets
            4. Real-world examples or use cases
            5. Any related concepts or terminology
            
            Make it professional yet accessible.
            """
            
            # Create chat history
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a helpful trading assistant that provides clear explanations.")
            chat_history.add_user_message(explanation_prompt)
            
            # Create settings
            settings = OpenAIChatPromptExecutionSettings(
                service_id="azure_gpt4o",
                max_tokens=1000,
                temperature=0.7
            )
            
            # Generate response
            logger.info("💥 Generating LLM response for concept explanation")
            result = await self.chat_service.get_chat_message_contents(
                chat_history=chat_history,
                settings=settings
            )
            
            if result and len(result) > 0:
                logger.info("💥 Concept explanation generated successfully")
                return f"**Explanation of '{concept}':**\n\n{result[0].content}"
            
            logger.warning("💥 Could not generate explanation")
            return f"Could not generate explanation for '{concept}'."
            
        except Exception as e:
            logger.error(f"💥 Error explaining concept: {str(e)}")
            return f"I apologize, but I encountered an error while explaining '{concept}': {str(e)}"

    @kernel_function(
        name="execute_custom_query", 
        description="Execute a specific SQL query on the database"
    )
    async def execute_custom_query(self, sql_query: str) -> str:
        """Execute custom SQL query"""
        logger.info(f"💥 execute_custom_query called with SQL: {sql_query[:100]}...")
        
        try:
            logger.info(f"💥 Executing custom SQL: {sql_query[:100]}...")
            
            if not self._validate_sql_query(sql_query):
                logger.warning("💥 SQL query validation failed")
                return "For safety, only SELECT queries are allowed."
            
            result_text, _ = await self._execute_sql_query(sql_query, "Custom SQL Query")
            return result_text
            
        except Exception as e:
            error_msg = f"💥 Error executing custom query: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def _validate_sql_query(self, sql_query: str) -> bool:
        """Validate SQL query for safety"""
        logger.info(f"💥 _validate_sql_query called with SQL: {sql_query[:50]}...")
        
        sql_lower = sql_query.lower().strip()
        
        destructive_keywords = [
            "drop", "delete", "update", "insert", "alter", "truncate", 
            "create", "modify", "grant", "revoke"
        ]
        
        if any(keyword in sql_lower for keyword in destructive_keywords):
            logger.warning("💥 SQL validation failed: destructive keywords found")
            return False
        
        if not (sql_lower.startswith('select') or sql_lower.startswith('with')):
            logger.warning("💥 SQL validation failed: not a SELECT or WITH query")
            return False
        
        logger.info("💥 SQL validation passed")
        return True

    def register_functions(self):
        """Register functions with the kernel"""
        logger.info("💥 Registering functions...")
        
        self.kernel.add_function(
            plugin_name="trading_assistant", 
            function_name="query_trade_data", 
            function=self.query_trade_data
        )
        self.kernel.add_function(
            plugin_name="trading_assistant", 
            function_name="explain_concept", 
            function=self.explain_concept
        )
        self.kernel.add_function(
            plugin_name="trading_assistant", 
            function_name="execute_custom_query", 
            function=self.execute_custom_query
        )
        
        self.functions_registered = True
        logger.info("💥 All functions registered successfully")

    async def _analyze_prompt_intent(self, prompt: str) -> str:
        """Analyze the prompt intent using keyword matching"""
        logger.info(f"💥 _analyze_prompt_intent called with prompt: '{prompt[:50]}...'")
        
        prompt_lower = prompt.lower()
        
        # Conceptual questions
        if any(word in prompt_lower for word in ["what is", "explain", "define", "how does", "tell me about"]):
            logger.info("💥 Intent detected: explain")
            return "explain"
        
        # Data queries
        data_patterns = [
            "show", "get", "list", "find", "query", "select",
            "how many", "what are the", "give me", "display",
            "trades", "deals", "transactions", "records", "data"
        ]
        
        if any(pattern in prompt_lower for pattern in data_patterns):
            logger.info("💥 Intent detected: data_query")
            return "data_query"
        
        # SQL queries
        if "select" in prompt_lower and ("from" in prompt_lower or "where" in prompt_lower):
            logger.info("💥 Intent detected: custom_query")
            return "custom_query"
        
        logger.info("💥 Intent detected: direct (general conversation)")
        return "direct"

    async def _get_llm_response(self, prompt: str, context: Dict) -> str:
        """Get response from LLM for general conversation"""
        logger.info(f"💥 _get_llm_response called with prompt: '{prompt[:50]}...'")
        
        try:
            if not self.chat_service:
                logger.error("💥 LLM service not available")
                return "LLM service not available for general conversation."
            
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a helpful trading assistant.")
            chat_history.add_user_message(prompt)
            
            settings = OpenAIChatPromptExecutionSettings(
                service_id="azure_gpt4o",
                max_tokens=1000,
                temperature=0.7
            )
            
            logger.info("💥 Generating LLM response for general conversation")
            result = await self.chat_service.get_chat_message_contents(
                chat_history=chat_history,
                settings=settings
            )
            
            if result and len(result) > 0:
                logger.info("💥 LLM response generated successfully")
                return str(result[0].content)
            
            logger.warning("💥 Could not generate LLM response")
            return "Could not generate response."
                
        except Exception as e:
            logger.error(f"💥 Error getting LLM response: {str(e)}")
            return f"Error generating response: {str(e)}"

    async def execute_with_function_calling(self, prompt: str, conversation_id: str = "default") -> str:
        """Intelligently route requests using intent analysis"""
        logger.info(f"💥 execute_with_function_calling called with prompt: '{prompt[:50]}...', conversation_id: {conversation_id}")
        
        context = self._get_conversation_context(conversation_id)
        context["messages"].append({
            "role": "user", 
            "content": prompt, 
            "timestamp": time.time()
        })
        
        try:
            # Analyze the prompt intent
            intent = await self._analyze_prompt_intent(prompt)
            logger.info(f"💥 Detected intent: {intent} for prompt: {prompt[:50]}...")
            
            if intent == "explain":
                # Extract the concept to explain
                concept = prompt
                if "what is" in prompt.lower():
                    concept = prompt.lower().split("what is")[-1].strip()
                elif "explain" in prompt.lower():
                    concept = prompt.lower().split("explain")[-1].strip()
                elif "define" in prompt.lower():
                    concept = prompt.lower().split("define")[-1].strip()
                
                logger.info(f"💥 Explaining concept: '{concept}'")
                result = await self.explain_concept(concept)
            
            elif intent == "data_query":
                logger.info("💥 Handling data query")
                result = await self.query_trade_data(prompt)
            
            elif intent == "custom_query":
                logger.info("💥 Handling custom SQL query")
                result = await self.execute_custom_query(prompt)
            
            else:  # direct or general conversation
                logger.info("💥 Handling general conversation")
                result = await self._get_llm_response(prompt, context)
            
            context["messages"].append({
                "role": "assistant", 
                "content": str(result), 
                "timestamp": time.time()
            })
            
            logger.info("💥 Function calling execution completed successfully")
            return str(result)
            
        except Exception as e:
            error_msg = f"💥 Error processing request: {str(e)}"
            logger.error(error_msg)
            
            context["messages"].append({
                "role": "assistant", 
                "content": error_msg, 
                "timestamp": time.time()
            })
            
            return error_msg

    async def _generate_visualization_if_needed(self, query: str, raw_data: List[Dict]) -> Optional[Dict]:
        """Generate visualization if the query suggests charting is needed"""
        logger.info(f"💥 _generate_visualization_if_needed called with query: '{query[:50]}...' and {len(raw_data)} data rows")
        
        try:
            # Check if visualization is appropriate based on query
            query_lower = query.lower()
            visualization_keywords = [
                "chart", "graph", "plot", "visualize", "show me",
                "trend", "distribution", "percentage", "compare",
                "top", "best", "worst", "ranking", "analyze",
                "histogram", "bar chart", "line chart", "pie chart"
            ]
            
            visualization_requested = any(keyword in query_lower for keyword in visualization_keywords)
            
            if not visualization_requested:
                logger.info("💥 Visualization not requested based on query keywords")
                return None
            
            # Import locally to avoid circular imports
            try:
                from .visualization_service import visualization_service
            except ImportError:
                try:
                    from visualization_service import visualization_service
                except ImportError as e:
                    logger.warning(f"💥 Visualization service not available: {e}")
                    return None
            
            if not raw_data:
                logger.warning("💥 No raw data available for visualization")
                return None
            
            # Generate the actual visualization using the raw data
            logger.info("💥 Generating visualization with raw data")
            chart_data = visualization_service.generate_chart(raw_data, query, f"Visualization: {query}")
            
            if chart_data:
                logger.info("💥 Visualization generated successfully")
                return chart_data
            else:
                logger.warning("💥 Visualization service failed to generate chart")
                return None
                
        except Exception as e:
            logger.error(f"💥 Error in visualization generation: {str(e)}")
            return None

# Available functions for capabilities endpoint
AVAILABLE_FUNCTIONS = [
    {
        "name": "query_trade_data",
        "description": "Query trade and deal information from database using natural language",
        "parameters": {
            "type": "object",
            "properties": {
                "natural_language_query": {
                    "type": "string", 
                    "description": "Natural language query describing what data to retrieve"
                }
            }
        }
    },
    {
        "name": "explain_concept",
        "description": "Explain trading concepts and definitions",
        "parameters": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string", 
                    "description": "Concept to explain"
                }
            }
        }
    },
    {
        "name": "execute_custom_query",
        "description": "Execute specific SQL query on database",
        "parameters": {
            "type": "object",
            "properties": {
                "sql_query": {
                    "type": "string", 
                    "description": "SQL query to execute"
                }
            }
        }
    }
]