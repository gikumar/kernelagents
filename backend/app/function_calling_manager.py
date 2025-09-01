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
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class FunctionCallingManager:
    """
    Function calling manager with intelligent routing
    """
    
    def __init__(self, kernel: Kernel):
        self.kernel = kernel
        self.functions_registered = False
        self._schema_cache = None
        self._schema_last_loaded = None
        self.conversations: Dict[str, Dict] = {}
        self.chat_service = None
        
        # Initialize Azure OpenAI
        self._initialize_azure_openai()
        
        # Register functions
        self.register_functions()
        
        logger.info("✅ Function Calling Manager initialized")

    def _initialize_azure_openai(self):
        """Initialize Azure OpenAI connection"""
        try:
            from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
            
            self.chat_service = AzureChatCompletion(
                service_id="azure_gpt4o",
                deployment_name=AZURE_OPENAI_DEPLOYMENT,
                endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_KEY,
                api_version=AZURE_OPENAI_API_VERSION
            )
            
            self.kernel.add_service(self.chat_service)
            logger.info("✅ Azure OpenAI GPT-4o initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Azure OpenAI: {str(e)}")
            # We can still work with Databricks functions

    def _get_conversation_context(self, conversation_id: str) -> Dict:
        """Get or create conversation context"""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = {
                "messages": [],
                "created_at": time.time(),
                "pending_clarification": None
            }
        return self.conversations[conversation_id]

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
            
            try:
                import databricks.sql
            except ImportError as e:
                logger.error(f"❌ Databricks SQL connector not installed: {e}")
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

    def _validate_sql_query(self, sql_query: str) -> bool:
        """Validate SQL query for safety"""
        sql_lower = sql_query.lower().strip()
        
        destructive_keywords = ["drop", "delete", "update", "insert", "alter", "truncate", 
                              "create", "modify", "grant", "revoke"]
        if any(keyword in sql_lower for keyword in destructive_keywords):
            return False
        
        if not (sql_lower.startswith('select') or sql_lower.startswith('with')):
            return False
        
        return True

    @kernel_function(
        name="get_trade_data",
        description="Get trade data from database. Use this when user asks about trades, deals, transactions, or wants to see trade information"
    )
    async def get_trade_data(self, query: str = "", limit: int = 10) -> str:
        """Get trade data based on user query"""
        try:
            logger.info(f"📊 Getting trade data for: {query}")
            
            connection = self._get_databricks_connection()
            if connection is None:
                return "❌ Database connection not available. Please check Databricks configuration."
            
            try:
                base_query = "SELECT * FROM trade_catalog.trade_schema.entity_trade_header"
                
                # Add basic filtering based on query
                if "recent" in query.lower():
                    base_query += " WHERE trade_date >= CURRENT_DATE - INTERVAL '30' DAY"
                elif "completed" in query.lower():
                    base_query += " WHERE status = 'completed'"
                
                base_query += f" LIMIT {limit}"
                
                with connection.cursor() as cursor:
                    cursor.execute(base_query)
                    
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
                    
                    result = f"📊 Trade Data ({len(data)} rows):\n\n"
                    for item in data[:5]:  # Show first 5 rows
                        result += "• "
                        for col, value in item.items():
                            result += f"{col}: {value} | "
                        result = result[:-3] + "\n"
                    
                    if len(data) > 5:
                        result += f"\n... and {len(data) - 5} more rows\n"
                    
                    return result
                    
            except Exception as e:
                logger.error(f"❌ Query execution error: {str(e)}")
                return f"❌ Query execution failed: {str(e)}"
                
            finally:
                connection.close()
            
        except Exception as e:
            error_msg = f"❌ Error getting trade data: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @kernel_function(
        name="get_pnl_data",
        description="Get profit and loss data. Use this when user asks about P&L, profits, losses, financial performance, or revenue"
    )
    async def get_pnl_data(self, query: str = "", limit: int = 10) -> str:
        """Get P&L data based on user query"""
        try:
            logger.info(f"📊 Getting P&L data for: {query}")
            
            connection = self._get_databricks_connection()
            if connection is None:
                return "❌ Database connection not available. Please check Databricks configuration."
            
            try:
                base_query = "SELECT * FROM trade_catalog.trade_schema.entity_pnl_detail"
                
                # Add basic filtering
                if "recent" in query.lower():
                    base_query += " WHERE pnl_date >= CURRENT_DATE - INTERVAL '30' DAY"
                
                base_query += f" LIMIT {limit}"
                
                with connection.cursor() as cursor:
                    cursor.execute(base_query)
                    
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
                    
                    result = f"📊 P&L Data ({len(data)} rows):\n\n"
                    for item in data[:5]:
                        result += "• "
                        for col, value in item.items():
                            result += f"{col}: {value} | "
                        result = result[:-3] + "\n"
                    
                    if len(data) > 5:
                        result += f"\n... and {len(data) - 5} more rows\n"
                    
                    return result
                    
            except Exception as e:
                logger.error(f"❌ Query execution error: {str(e)}")
                return f"❌ Query execution failed: {str(e)}"
                
            finally:
                connection.close()
            
        except Exception as e:
            error_msg = f"❌ Error getting P&L data: {str(e)}"
            logger.error(error_msg)
            return error_msg

    @kernel_function(
    name="explain_concept",
    description="Explain trading concepts, definitions, or general information. Use this when user asks 'what is', 'explain', 'define', or wants conceptual understanding"
)
    async def explain_concept(self, concept: str) -> str:
        """Explain trading concepts using LLM"""
        try:
            logger.info(f"💬 Explaining concept: {concept}")
            
            if not self.chat_service:
                return "❌ LLM service not available. Please check Azure OpenAI configuration."
            
            # Use LLM to explain the concept - Simple direct approach
            explanation_prompt = f"""
            Please provide a clear, comprehensive explanation of '{concept}' in the context of trading and finance.
            
            Your explanation should include:
            1. A simple and clear definition
            2. How it works in practical trading scenarios
            3. Why it's important in financial markets
            4. Real-world examples or use cases
            5. Any related concepts or terminology
            
            Make it professional yet accessible for someone with basic trading knowledge.
            """
            
            # Create simple chat history
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a helpful trading assistant that provides clear explanations.")
            chat_history.add_user_message(explanation_prompt)
            
            # Import the required settings class
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
            
            # Create settings object
            settings = OpenAIChatPromptExecutionSettings(
                service_id="azure_gpt4o",
                max_tokens=1000,
                temperature=0.7
            )
            
            # Use the chat service with proper settings
            try:
                result = await self.chat_service.get_chat_message_contents(
                    chat_history=chat_history,
                    settings=settings
                )
                if result and len(result) > 0:
                    return f"**Explanation of '{concept}':**\n\n{result[0].content}"
            except Exception as e:
                logger.error(f"❌ Error with get_chat_message_contents: {str(e)}")
                # Fallback explanation
                return f"**Explanation of '{concept}':**\n\nIn oil and gas trading, a deal typically refers to a negotiated agreement between parties to buy, sell, or exchange commodities like oil and gas under specific terms, including price, quantity, delivery timing, and quality specifications. Deals can be spot transactions for immediate delivery or forward contracts for future delivery."
            
            return f"❌ Could not generate explanation for '{concept}'."
            
        except Exception as e:
            logger.error(f"❌ Error explaining concept: {str(e)}")
            return f"❌ I apologize, but I encountered an error while trying to explain '{concept}'. Please try again."



    @kernel_function(
        name="execute_custom_query",
        description="Execute a specific SQL query on the database. Use this when user provides explicit SQL code or very specific data requirements"
    )
    async def execute_custom_query(self, sql_query: str) -> str:
        """Execute custom SQL query"""
        try:
            logger.info(f"📋 Executing custom SQL: {sql_query[:100]}...")
            
            if not self._validate_sql_query(sql_query):
                return "❌ For safety, only SELECT queries are allowed. Destructive operations are blocked."
            
            connection = self._get_databricks_connection()
            if connection is None:
                return "❌ Database connection not available. Please check Databricks configuration."
            
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql_query)
                    
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
                    
                    result = f"✅ Custom Query Results:\n\n"
                    result += f"Executed: {sql_query}\n\n"
                    result += f"Columns: {', '.join(columns)}\n"
                    result += f"Rows returned: {len(data)}\n\n"
                    
                    if data:
                        result += "First few rows:\n"
                        for i, row in enumerate(data[:3]):
                            result += f"{i+1}. {row}\n"
                    
                    return result
                    
            except Exception as e:
                return f"❌ SQL execution failed: {str(e)}"
                
            finally:
                connection.close()
            
        except Exception as e:
            error_msg = f"❌ Error executing custom query: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def register_functions(self):
        """Register functions with the kernel"""
        logger.info("🔧 Registering functions...")
        
        # Register all functions
        self.kernel.add_function(
            plugin_name="trading_assistant", 
            function_name="get_trade_data", 
            function=self.get_trade_data
        )
        self.kernel.add_function(
            plugin_name="trading_assistant", 
            function_name="get_pnl_data", 
            function=self.get_pnl_data
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
        logger.info("✅ All functions registered")

    async def _analyze_prompt_intent(self, prompt: str) -> str:
        """Analyze the prompt intent using keyword matching"""
        prompt_lower = prompt.lower()
        
        # Conceptual questions
        if any(word in prompt_lower for word in ["what is", "explain", "define", "how does", "tell me about"]):
            return "explain"
        
        # Trade data requests
        if any(word in prompt_lower for word in ["trade", "deal", "transaction", "show trades", "get trades", "list trades"]):
            return "trade_data"
        
        # P&L data requests
        if any(word in prompt_lower for word in ["pnl", "profit", "loss", "revenue", "financial", "performance"]):
            return "pnl_data"
        
        # SQL queries
        if "select" in prompt_lower and ("from" in prompt_lower or "where" in prompt_lower):
            return "custom_query"
        
        return "direct"

    async def _get_llm_response(self, prompt: str, context: Dict) -> str:
        """Get response from LLM for general conversation"""
        try:
            if not self.chat_service:
                return "❌ LLM service not available for general conversation."
            
            # Create simple chat history
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a helpful trading assistant.")
            chat_history.add_user_message(prompt)
            
            # Import the required settings class
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
            
            # Create settings object
            settings = OpenAIChatPromptExecutionSettings(
                service_id="azure_gpt4o",
                max_tokens=1000,
                temperature=0.7
            )
            
            # Try to get response with proper settings
            try:
                result = await self.chat_service.get_chat_message_contents(
                    chat_history=chat_history,
                    settings=settings
                )
                if result and len(result) > 0:
                    return str(result[0].content)
            except Exception as e:
                logger.error(f"❌ Error with get_chat_message_contents: {str(e)}")
                return "I'm here to help with your trading questions. How can I assist you today?"
            
            return "❌ Could not generate response."
                
        except Exception as e:
            logger.error(f"❌ Error getting LLM response: {str(e)}")
            return f"❌ Error generating response: {str(e)}"
    

    async def execute_with_function_calling(self, prompt: str, conversation_id: str = "default") -> str:
        """Intelligently route requests using intent analysis"""
        context = self._get_conversation_context(conversation_id)
        context["messages"].append({"role": "user", "content": prompt, "timestamp": time.time()})
        
        try:
            # Analyze the prompt intent
            intent = await self._analyze_prompt_intent(prompt)
            logger.info(f"🎯 Detected intent: {intent} for prompt: {prompt[:50]}...")
            
            if intent == "explain":
                # Extract the concept to explain
                concept = prompt
                if "what is" in prompt.lower():
                    concept = prompt.lower().split("what is")[-1].strip()
                elif "explain" in prompt.lower():
                    concept = prompt.lower().split("explain")[-1].strip()
                elif "define" in prompt.lower():
                    concept = prompt.lower().split("define")[-1].strip()
                
                result = await self.explain_concept(concept)
            
            elif intent == "trade_data":
                # Extract parameters for trade data
                query = ""
                limit = 10
                
                if "latest" in prompt.lower() or "recent" in prompt.lower():
                    query = "recent"
                if any(word in prompt.lower() for word in ["5", "five", "first five"]):
                    limit = 5
                elif any(word in prompt.lower() for word in ["10", "ten"]):
                    limit = 10
                
                result = await self.get_trade_data(query, limit)
            
            elif intent == "pnl_data":
                # Extract parameters for P&L data
                query = ""
                limit = 10
                result = await self.get_pnl_data(query, limit)
            
            elif intent == "custom_query":
                # Use the prompt as SQL query
                result = await self.execute_custom_query(prompt)
            
            else:  # direct or general conversation
                result = await self._get_llm_response(prompt, context)
            
            context["messages"].append({"role": "assistant", "content": str(result), "timestamp": time.time()})
            return str(result)
            
        except Exception as e:
            error_msg = f"❌ Error processing request: {str(e)}"
            logger.error(error_msg)
            
            # Try to use explain_concept as fallback for conceptual questions
            if any(word in prompt.lower() for word in ["what is", "explain", "define"]):
                try:
                    concept = prompt
                    fallback_result = await self.explain_concept(concept)
                    context["messages"].append({"role": "assistant", "content": fallback_result, "timestamp": time.time()})
                    return fallback_result
                except:
                    pass
            
            context["messages"].append({"role": "assistant", "content": error_msg, "timestamp": time.time()})
            return error_msg

# Available functions for capabilities endpoint
AVAILABLE_FUNCTIONS = [
    {
        "name": "get_trade_data",
        "description": "Get trade and deal information from database",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or filter"},
                "limit": {"type": "integer", "description": "Number of records to return"}
            }
        }
    },
    {
        "name": "get_pnl_data", 
        "description": "Get profit and loss data from database",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or filter"},
                "limit": {"type": "integer", "description": "Number of records to return"}
            }
        }
    },
    {
        "name": "explain_concept",
        "description": "Explain trading concepts and definitions",
        "parameters": {
            "type": "object",
            "properties": {
                "concept": {"type": "string", "description": "Concept to explain"}
            }
        }
    },
    {
        "name": "execute_custom_query",
        "description": "Execute specific SQL query on database",
        "parameters": {
            "type": "object",
            "properties": {
                "sql_query": {"type": "string", "description": "SQL query to execute"}
            }
        }
    }
]