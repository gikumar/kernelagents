# backend/app/plugins/trading_plugin.py
from .base_plugin import BasePlugin
from semantic_kernel.functions import kernel_function

from typing import Dict, List, Optional, Any, Tuple
import json
import logging
import time
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

class TradingPlugin(BasePlugin):  # CORRECTED: BasePlugin instead of BaseAgent
    def __init__(self, kernel):
        super().__init__(kernel, "TradingPlugin")
        self.sql_generator = None
        self.conversations: Dict[str, Dict] = {}
        self.chat_service = None
    
    async def initialize(self):
        """Initialize trading plugin"""
        logger.info("⭐ TradingPlugin.initialize() - Entry")
        try:
            # Initialize Azure OpenAI service
            await self._initialize_azure_openai()
            
            # SQL Generator will be initialized lazily to save costs
            # Uncomment when needed
            self.sql_generator = await self._initialize_sql_generator()  
            
            logger.info("⭐ TradingPlugin.initialize() - Success")
            
        except Exception as e:
            logger.error(f"💥 TradingPlugin.initialize() - Failed: {str(e)}")
            raise
        finally:
            logger.info("⭐ TradingPlugin.initialize() - Exit")
    
    
    async def _initialize_azure_openai(self):
        """Initialize Azure OpenAI connection"""
        logger.info("⭐ _initialize_azure_openai() - Entry")
        try:
            from app.core.config_manager import config
            
            # Check if service already exists in kernel
            try:
                self.chat_service = self.kernel.get_service("azure_gpt4o")
                logger.info("⭐ Azure OpenAI service already exists in kernel, reusing it")
                return
            except ValueError:
                logger.info("⭐ Creating new Azure OpenAI service")
                pass
            
            if not all([config.AZURE_OPENAI_ENDPOINT, config.AZURE_OPENAI_KEY, config.AZURE_OPENAI_DEPLOYMENT]):
                raise ValueError("Missing required Azure OpenAI configuration")
            
            from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
            
            self.chat_service = AzureChatCompletion(
                service_id="azure_gpt4o",
                deployment_name=config.AZURE_OPENAI_DEPLOYMENT,
                endpoint=config.AZURE_OPENAI_ENDPOINT,
                api_key=config.AZURE_OPENAI_KEY,
                api_version=config.AZURE_OPENAI_API_VERSION
            )
            
            self.kernel.add_service(self.chat_service)
            logger.info("⭐ Azure OpenAI GPT-4o initialized successfully")
            
        except Exception as e:
            logger.error(f"💥 _initialize_azure_openai() - Failed: {str(e)}")
            raise
        finally:
            logger.info("⭐ _initialize_azure_openai() - Exit")
    
    async def _initialize_sql_generator(self):
        """Initialize SQL generator"""
        logger.info("⭐ _initialize_sql_generator() - Entry")
        try:
            from app.utils.sql_generator import SQLGenerator
            sql_generator = SQLGenerator()
            logger.info("⭐ SQL Generator initialized successfully")
            return sql_generator
        except Exception as e:
            logger.error(f"💥 _initialize_sql_generator() - Failed: {str(e)}")
            raise
        finally:
            logger.info("⭐ _initialize_sql_generator() - Exit")

    def _get_conversation_context(self, conversation_id: str) -> Dict:
        """Get or create conversation context"""
        logger.info(f"⭐ _get_conversation_context() - Entry: {conversation_id}")
        try:
            if conversation_id not in self.conversations:
                logger.info(f"⭐ Decision: Creating new conversation context for ID: {conversation_id}")
                self.conversations[conversation_id] = {
                    "messages": [],
                    "created_at": time.time(),
                    "pending_clarification": None,
                    "last_query": None,
                    "query_history": []
                }
            return self.conversations[conversation_id]
        finally:
            logger.info("⭐ _get_conversation_context() - Exit")

    def _update_conversation_context(self, conversation_id: str, query: str, response: str):
        """Update conversation context with new interaction"""
        logger.info(f"⭐ _update_conversation_context() - Entry: {conversation_id}")
        try:
            conversation_ctx = self._get_conversation_context(conversation_id)
            
            # Store the interaction
            conversation_ctx["messages"].append({
                "role": "user",
                "content": query,
                "timestamp": time.time()
            })
            
            conversation_ctx["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": time.time()
            })
            
            conversation_ctx["last_query"] = query
            conversation_ctx["query_history"].append({
                "query": query,
                "timestamp": time.time(),
                "response_preview": response[:100] + "..." if len(response) > 100 else response
            })
            
            logger.info(f"⭐ Conversation context updated with new interaction")
        except Exception as e:
            logger.error(f"💥 Error updating conversation context: {str(e)}")
        finally:
            logger.info("⭐ _update_conversation_context() - Exit")

    def _get_databricks_connection(self):
        """Get Databricks connection with error handling"""
        logger.info("⭐ _get_databricks_connection() - Entry")
        try:
            from app.core.config_manager import config
            import databricks.sql
            
            if not all([config.DATABRICKS_SERVER_HOSTNAME, config.DATABRICKS_ACCESS_TOKEN, config.DATABRICKS_HTTP_PATH]):
                logger.error("⭐ Databricks connection parameters not configured")
                return None
            
            logger.info(f"⭐ Connecting to Databricks: {config.DATABRICKS_SERVER_HOSTNAME}")
            connection = databricks.sql.connect(
                server_hostname=config.DATABRICKS_SERVER_HOSTNAME,
                http_path=config.DATABRICKS_HTTP_PATH,
                access_token=config.DATABRICKS_ACCESS_TOKEN
            )
            
            logger.info("⭐ Connected to Databricks successfully")
            return connection
            
        except ImportError as e:
            logger.error(f"💥 Databricks SQL connector not installed: {e}")
            return None
        except Exception as e:
            logger.error(f"💥 Failed to connect to Databricks: {str(e)}")
            return None
        finally:
            logger.info("⭐ _get_databricks_connection() - Exit")


    @kernel_function(
    name="query_trade_data",
    description="Query trade data from database using natural language. Use this when user asks about trades, deals, transactions, or wants to see trade information"
)
    async def query_trade_data(self, natural_language_query: str = "") -> str:
        """Query trade data using natural language to SQL conversion"""
        logger.info(f"⭐ query_trade_data() - Entry: '{natural_language_query[:50]}...'")
        
        # Get context from the trading agent
        try:
            from app.agents.trading_agent import TradingAgent
            trading_agent = None
            
            # Find the trading agent instance (this is a bit hacky but works)
            for service in self.kernel.get_services():
                if isinstance(service, TradingAgent):
                    trading_agent = service
                    break
            
            if trading_agent and hasattr(trading_agent, 'current_context'):
                context = trading_agent.current_context
                conversation_id = context.get('conversation_id', 'default')
            else:
                conversation_id = 'default'
                context = {}
                
        except Exception as e:
            logger.warning(f"⭐ Could not get context from trading agent: {str(e)}")
            conversation_id = 'default'
            context = {}
        
        conversation_ctx = self._get_conversation_context(conversation_id)
        
        try:
            logger.info(f"⭐ Processing natural language query: {natural_language_query}")
            logger.info(f"⭐ Conversation ID: {conversation_id}, Context messages: {len(conversation_ctx['messages'])}")
            
            # Add conversation context to the query if available
            enhanced_query = self._enhance_query_with_context(natural_language_query, conversation_ctx)
            if enhanced_query != natural_language_query:
                logger.info(f"⭐ Enhanced query with conversation context")
            
            if not self.sql_generator:
                logger.error("⭐ SQL Generator not available - cost saving mode")
                response = "SQL query generation is currently disabled to save costs. Please try again later or use direct SQL queries with the execute_custom_query function."
                self._update_conversation_context(conversation_id, natural_language_query, response)
                return response
            
            # Generate SQL from natural language
            logger.info("⭐ Generating SQL from natural language")
            sql_query = await self.sql_generator.generate_sql_from_natural_language(
                enhanced_query, self.kernel
            )
            
            logger.info(f"⭐ Generated SQL: {sql_query}")
            
            # If SQL generation failed, provide a helpful response
            if "error" in sql_query.lower() or "not available" in sql_query.lower():
                logger.warning(f"⭐ SQL generation failed: {sql_query}")
                response = f"I couldn't generate a valid SQL query for your request. Please try rephrasing your question. Error: {sql_query}"
                self._update_conversation_context(conversation_id, natural_language_query, response)
                return response
            
            # Execute the query and get results
            logger.info("⭐ Executing SQL query")
            result_text, raw_data = await self._execute_sql_query(sql_query, natural_language_query)
            
            # Generate visualization if appropriate
            logger.info("⭐ Checking if visualization is needed")
            chart_data = await self._generate_visualization_if_needed(natural_language_query, raw_data)
            
            if chart_data:
                logger.info("⭐ Visualization generated successfully, returning JSON response")
                response_data = {
                    "text_response": result_text,
                    "visualization": chart_data,
                    "has_chart": True
                }
                response = json.dumps(response_data)
            else:
                logger.info("⭐ No visualization needed, returning text response only")
                response = result_text
            
            # Update conversation context with this interaction
            self._update_conversation_context(conversation_id, natural_language_query, response)
                
            return response
                
        except Exception as e:
            error_msg = f"💥 Error processing query: {str(e)}"
            logger.error(error_msg)
            response = f"I encountered an error while processing your request. Please try again or rephrase your question. Error: {str(e)}"
            self._update_conversation_context(conversation_id, natural_language_query, response)
            return response
        finally:
            logger.info("⭐ query_trade_data() - Exit")

    def _enhance_query_with_context(self, query: str, conversation_ctx: Dict) -> str:
        """Enhance the query with conversation context for better follow-ups"""
        if not conversation_ctx.get("messages"):
            return query
        
        # Build context from recent conversation
        context_parts = []
        for msg in conversation_ctx["messages"][-6:]:  # Last 3 exchanges
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")
        
        context_str = "\n".join(context_parts)
        return f"Previous conversation:\n{context_str}\n\nCurrent question: {query}"

    async def _execute_sql_query(self, sql_query: str, original_query: str = "") -> Tuple[str, Optional[List[Dict]]]:
        """Execute SQL query and return both formatted results and raw data"""
        logger.info(f"⭐ _execute_sql_query() - Entry: {sql_query[:100]}...")
        
        connection = self._get_databricks_connection()
        if connection is None:
            logger.error("⭐ Database connection not available")
            return "Database connection not available. Please check Databricks configuration.", None
        
        try:
            with connection.cursor() as cursor:
                logger.info("⭐ Executing SQL cursor")
                cursor.execute(sql_query)
                
                columns = [desc[0] for desc in cursor.description]
                raw_data = []
                formatted_data = []
                
                logger.info(f"⭐ Fetching results with {len(columns)} columns: {columns}")
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
                logger.info("⭐ Formatting query results")
                result_text = self._format_query_results(formatted_data, columns, sql_query, original_query)
                logger.info(f"⭐ Query executed successfully, returned {len(raw_data)} rows")
                return result_text, raw_data
                
        except Exception as e:
            logger.error(f"💥 Query execution error: {str(e)}")
            return f"Query execution failed: {str(e)}", None
            
        finally:
            connection.close()
            logger.info("⭐ Database connection closed")
            logger.info("⭐ _execute_sql_query() - Exit")

    def _format_query_results(self, data: list, columns: list, sql_query: str, original_query: str) -> str:
        """Format query results intelligently"""
        logger.info(f"⭐ _format_query_results() - Entry: {len(data)} rows")
        
        if not data:
            logger.info("⭐ No data found for query")
            return f"No results found for: '{original_query}'\n\nQuery: {sql_query}"
        
        result = f"Query Results ({len(data)} row{'s' if len(data) != 1 else ''}):\n\n"
        
        # Decision: Format based on data size
        if len(data) <= 5 and len(columns) <= 8:
            logger.info("⭐ Decision: Using detailed table format")
            result += self._format_detailed_table(data, columns)
        else:
            logger.info("⭐ Decision: Using compact table format")
            result += self._format_compact_table(data, columns)
        
        # Add query context
        result += f"\nGenerated from: '{original_query}'\n"
        result += f"SQL: {sql_query}\n"
        
        logger.info("⭐ Query results formatted successfully")
        logger.info("⭐ _format_query_results() - Exit")
        return result

    def _format_detailed_table(self, data: list, columns: list) -> str:
        """Format data as a detailed table"""
        logger.info("⭐ _format_detailed_table() - Entry")
        result = ""
        for i, row in enumerate(data, 1):
            result += f"**Row {i}:**\n"
            for col in columns:
                value = row.get(col, "N/A")
                if value and len(str(value)) > 100:
                    value = str(value)[:100] + "..."
                result += f"  • {col}: {value}\n"
            result += "\n"
        logger.info("⭐ Detailed table formatted")
        logger.info("⭐ _format_detailed_table() - Exit")
        return result

    def _format_compact_table(self, data: list, columns: list) -> str:
        """Format data as a compact table"""
        logger.info("⭐ _format_compact_table() - Entry")
        
        # Decision: Select key columns for display
        key_columns = self._get_key_columns(columns)
        logger.info(f"⭐ Selected key columns: {key_columns}")
        
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
        
        logger.info("⭐ Compact table formatted")
        logger.info("⭐ _format_compact_table() - Exit")
        return result

    def _get_key_columns(self, all_columns: list) -> list:
        """Identify key columns to display"""
        logger.info(f"⭐ _get_key_columns() - Entry: {all_columns}")
        
        key_columns = []
        priority_columns = [
            'deal_num', 'tran_num', 'trade_date', 'currency', 'amount', 
            'volume', 'price', 'trader', 'buy_sell', 'status'
        ]
        
        # Decision: Add priority columns that exist
        for col in priority_columns:
            if col in all_columns:
                key_columns.append(col)
        
        # Decision: Fill remaining slots
        if len(key_columns) < 6:
            additional_cols = [col for col in all_columns if col not in key_columns]
            key_columns.extend(additional_cols[:6 - len(key_columns)])
        
        logger.info(f"⭐ Final key columns selected: {key_columns}")
        logger.info("⭐ _get_key_columns() - Exit")
        return key_columns

    @kernel_function(
        name="explain_concept",
        description="Explain trading concepts, definitions, or general information"
    )
    async def explain_concept(self, concept: str, context: dict = None) -> str:
        """Explain trading concepts using LLM"""
        logger.info(f"⭐ explain_concept() - Entry: '{concept}'")
        
        try:
            # Extract conversation ID from context
            conversation_id = context.get('conversation_id', 'default') if context else 'default'
            conversation_ctx = self._get_conversation_context(conversation_id)
            
            logger.info(f"⭐ Explaining concept: {concept}")
            
            if not self.chat_service:
                logger.error("⭐ LLM service not available")
                response = "LLM service not available. Please check Azure OpenAI configuration."
                self._update_conversation_context(conversation_id, concept, response)
                return response
            
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
            from semantic_kernel.contents import ChatHistory
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
            
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
            logger.info("⭐ Generating LLM response for concept explanation")
            result = await self.chat_service.get_chat_message_contents(
                chat_history=chat_history,
                settings=settings
            )
            
            if result and len(result) > 0:
                logger.info("⭐ Concept explanation generated successfully")
                response = f"**Explanation of '{concept}':**\n\n{result[0].content}"
            else:
                logger.warning("⭐ Could not generate explanation")
                response = f"Could not generate explanation for '{concept}'."
            
            # Update conversation context
            self._update_conversation_context(conversation_id, concept, response)
            return response
            
        except Exception as e:
            logger.error(f"💥 Error explaining concept: {str(e)}")
            response = f"I apologize, but I encountered an error while explaining '{concept}': {str(e)}"
            self._update_conversation_context(conversation_id, concept, response)
            return response
        finally:
            logger.info("⭐ explain_concept() - Exit")

    @kernel_function(
        name="execute_custom_query", 
        description="Execute a specific SQL query on the database"
    )
    async def execute_custom_query(self, sql_query: str, context: dict = None) -> str:
        """Execute custom SQL query"""
        logger.info(f"⭐ execute_custom_query() - Entry: {sql_query[:100]}...")
        
        try:
            # Extract conversation ID from context
            conversation_id = context.get('conversation_id', 'default') if context else 'default'
            conversation_ctx = self._get_conversation_context(conversation_id)
            
            logger.info(f"⭐ Executing custom SQL: {sql_query[:100]}...")
            
            if not self._validate_sql_query(sql_query):
                logger.warning("⭐ SQL query validation failed")
                response = "For safety, only SELECT queries are allowed."
                self._update_conversation_context(conversation_id, sql_query, response)
                return response
            
            result_text, _ = await self._execute_sql_query(sql_query, "Custom SQL Query")
            
            # Update conversation context
            self._update_conversation_context(conversation_id, sql_query, result_text)
            return result_text
            
        except Exception as e:
            error_msg = f"💥 Error executing custom query: {str(e)}"
            logger.error(error_msg)
            self._update_conversation_context(conversation_id, sql_query, error_msg)
            return error_msg
        finally:
            logger.info("⭐ execute_custom_query() - Exit")

    def _validate_sql_query(self, sql_query: str) -> bool:
        """Validate SQL query for safety"""
        logger.info(f"⭐ _validate_sql_query() - Entry: {sql_query[:50]}...")
        
        sql_lower = sql_query.lower().strip()
        
        destructive_keywords = [
            "drop", "delete", "update", "insert", "alter", "truncate", 
            "create", "modify", "grant", "revoke"
        ]
        
        # Decision: Check for destructive keywords
        if any(keyword in sql_lower for keyword in destructive_keywords):
            logger.warning("⭐ SQL validation failed: destructive keywords found")
            return False
        
        # Decision: Only allow SELECT or WITH queries
        if not (sql_lower.startswith('select') or sql_lower.startswith('with')):
            logger.warning("⭐ SQL validation failed: not a SELECT or WITH query")
            return False
        
        logger.info("⭐ SQL validation passed")
        logger.info("⭐ _validate_sql_query() - Exit")
        return True

    async def _generate_visualization_if_needed(self, query: str, raw_data: List[Dict]) -> Optional[Dict]:
        """Generate visualization if the query suggests charting is needed"""
        logger.info(f"⭐ _generate_visualization_if_needed() - Entry: '{query[:50]}...' with {len(raw_data)} rows")
        
        try:
            # Decision: Check if visualization is appropriate based on query keywords
            query_lower = query.lower()
            visualization_keywords = [
                "chart", "graph", "plot", "visualize", "show me",
                "trend", "distribution", "percentage", "compare",
                "top", "best", "worst", "ranking", "analyze",
                "histogram", "bar chart", "line chart", "pie chart"
            ]
            
            visualization_requested = any(keyword in query_lower for keyword in visualization_keywords)
            
            if not visualization_requested:
                logger.info("⭐ Decision: Visualization not requested based on query keywords")
                return None
            
            # Import visualization service
            try:
                from app.utils.visualization_service import visualization_service
            except ImportError as e:
                logger.warning(f"⭐ Visualization service not available: {e}")
                return None
            
            if not raw_data:
                logger.warning("⭐ No raw data available for visualization")
                return None
            
            # Generate visualization
            logger.info("⭐ Generating visualization with raw data")
            chart_data = visualization_service.generate_chart(raw_data, query, f"Visualization: {query}")
            
            if chart_data:
                logger.info("⭐ Visualization generated successfully")
                return chart_data
            else:
                logger.warning("⭐ Visualization service failed to generate chart")
                return None
                
        except Exception as e:
            logger.error(f"💥 Error in visualization generation: {str(e)}")
            return None
        finally:
            logger.info("⭐ _generate_visualization_if_needed() - Exit")

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("⭐ TradingPlugin.cleanup() - Entry")
        try:
            self.conversations.clear()
            logger.info("⭐ Conversations cleared")
        except Exception as e:
            logger.error(f"💥 Error during cleanup: {str(e)}")
        finally:
            logger.info("⭐ TradingPlugin.cleanup() - Exit")

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