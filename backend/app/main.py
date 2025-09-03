# backend/app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from contextlib import asynccontextmanager
import logging
import traceback
from pathlib import Path
import json
from dotenv import load_dotenv
import asyncio

# Load .env from the backend directory first
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"✅ Loaded .env from: {env_path}")

def setup_logging():
    """Configure comprehensive logging"""
    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Set up root logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('app.log')  # Optional: also log to file
        ]
    )
    
    # Set specific levels for noisy modules if needed
    logging.getLogger('semantic_kernel').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

# Call this function before creating the FastAPI app
setup_logging()

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global variable for Azure AI agent
azure_ai_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application lifespan")
    
    # Ensure cache directory exists
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    # PAUSED: Schema loading to avoid costs
    # Will be resumed later when needed
    logger.info("⏸️  Schema loading paused to avoid costs - will resume when needed")
    
    # Initialize Azure AI Agent - USE AWAIT
    try:
        global azure_ai_agent
        azure_ai_agent = await initialize_azure_ai_agent()
        logger.info("✅ Azure AI Agent initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Azure AI Agent: {str(e)}")
        logger.error(traceback.format_exc())
    
    yield
    
    # Cleanup
    if azure_ai_agent:
        azure_ai_agent.cleanup()
    logger.info("🚀 Application shutdown")

async def initialize_azure_ai_agent():
    """Initialize Azure AI Agent with trading functionality"""
    logger.info("💥 Initializing Azure AI Agent")
    
    # Get configuration settings
    load_dotenv()
    
    # Import required modules
    from azure.identity import DefaultAzureCredential
    from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
    from semantic_kernel import Kernel
    
    # Create Azure AI Agent settings
    ai_agent_settings = AzureAIAgentSettings()
    
    # Create credentials (synchronous)
    credential = DefaultAzureCredential(
        exclude_environment_credential=True,
        exclude_managed_identity_credential=True
    )
    
    # Create Azure AI Agent client (synchronous)
    project_client = AzureAIAgent.create_client(credential=credential)
    
    # Define an Azure AI agent for trading assistance - USE AWAIT
    trading_agent_def = await project_client.agents.create_agent(
        model=ai_agent_settings.model_deployment_name,
        name="trading_assistant",
        instructions="""You are an AI assistant for trading and financial data analysis.
                        You can help users query trade data, explain trading concepts, 
                        execute custom SQL queries, and provide general trading assistance.
                        Use the available plugin functions to interact with databases and provide explanations."""
    )
    
    # Create semantic kernel
    kernel = Kernel()
    
    # Initialize Azure OpenAI service
    from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
    from config import (
        AZURE_OPENAI_ENDPOINT, 
        AZURE_OPENAI_KEY, 
        AZURE_OPENAI_DEPLOYMENT, 
        AZURE_OPENAI_API_VERSION
    )
    
    chat_service = AzureChatCompletion(
        service_id="azure_gpt4o",
        deployment_name=AZURE_OPENAI_DEPLOYMENT,
        endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    kernel.add_service(chat_service)
    
    # Initialize SQL Generator - COMMENTED OUT TO SAVE COSTS
    # from sql_generator import SQLGenerator
    # sql_generator = SQLGenerator()
    sql_generator = None  # Set to None to avoid costs
    logger.info("⏸️  SQL Generator initialization paused to avoid costs")
    
    # Create TradingPlugin with all the functionality from function_calling_manager
    trading_plugin = TradingPlugin(kernel, sql_generator)
    
    # Create the Azure AI Agent
    trading_agent = AzureAIAgent(
        client=project_client,
        definition=trading_agent_def,
        plugins=[trading_plugin, EmailPlugin()]
    )
    
    # Return agent with cleanup capability
    return AzureAIAgentWrapper(trading_agent, project_client, credential)

class AzureAIAgentWrapper:
    """Wrapper for Azure AI Agent with cleanup functionality"""
    def __init__(self, agent, client, credential):
        self.agent = agent
        self.client = client
        self.credential = credential
    
    async def get_response(self, prompt: str, conversation_id: str = "default"):
        """Get response from Azure AI Agent"""
        try:
            # Add the input prompt to a list of messages to be submitted
            prompt_messages = [prompt]
            
            # Invoke the agent for the specified thread with the messages
            response = await self.agent.get_response(prompt_messages)
            
            return str(response)
        except Exception as e:
            logger.error(f"Error getting agent response: {str(e)}")
            return f"I apologize, but I encountered an error: {str(e)}"
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.client.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

class TradingPlugin:
    """Plugin for trading functionality with all methods from function_calling_manager"""
    
    def __init__(self, kernel, sql_generator):
        self.kernel = kernel
        self.sql_generator = sql_generator
        self.conversations: Dict[str, Dict] = {}
        self.chat_service = kernel.get_service("azure_gpt4o")
    
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
            from semantic_kernel.contents import ChatHistory
            chat_history = ChatHistory()
            chat_history.add_system_message("You are a helpful trading assistant that provides clear explanations.")
            chat_history.add_user_message(explanation_prompt)
            
            # Create settings
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
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

class EmailPlugin:
    """Plugin for email functionality"""
    
    def send_email(self, to: str, subject: str, body: str) -> str:
        """Send an email (simulated)"""
        logger.info(f"💥 Sending email to: {to}, subject: {subject}")
        print(f"\nTo: {to}")
        print(f"Subject: {subject}")
        print(f"Body: {body}\n")
        return f"Email sent successfully to {to} with subject '{subject}'"

# Create the FastAPI app with lifespan
app = FastAPI(lifespan=lifespan, title="Azure AI Agent API")

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AskRequest(BaseModel):
    prompt: str
    agentMode: Optional[str] = "Balanced"
    conversation_id: Optional[str] = "default" 

class AskResponse(BaseModel):
    response: str
    status: str
    visualization: Optional[Dict] = None
    has_chart: Optional[bool] = False

@app.post("/ask", response_model=AskResponse)
async def ask_agent(request: AskRequest):
    """
    Endpoint that uses Azure AI Agent for intelligent response generation
    """
    logger.info(f"🚀 Received /ask request: {request.prompt[:100]}...")
    
    try:
        global azure_ai_agent
        if azure_ai_agent is None:
            raise HTTPException(status_code=500, detail="Azure AI Agent not initialized")
        
        result = await azure_ai_agent.get_response(request.prompt, request.conversation_id)
        
        # Check if result contains visualization data
        try:
            result_data = json.loads(result)
            if isinstance(result_data, dict) and "has_chart" in result_data:
                return AskResponse(
                    response=result_data.get("text_response", ""),
                    status="success",
                    visualization=result_data.get("visualization"),
                    has_chart=result_data.get("has_chart", False)
                )
        except json.JSONDecodeError:
            # If it's not JSON, it's a regular response
            pass
        
        return AskResponse(
            response=result,
            status="success",
            has_chart=False
        )

    except Exception as e:
        logger.error(f"Unexpected error in /ask: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Azure AI Agent Backend",
        "version": "2.0",
        "features": ["azure_ai_agent", "llm_conversation", "databricks_query", "function_calling"]
    }

@app.get("/diagnostics/detailed")
async def detailed_diagnostics():
    """Detailed diagnostic including environment variables"""
    try:
        # Check if .env file exists
        env_file = Path(__file__).parent / ".env"
        env_exists = env_file.exists()
        
        # Check actual environment variables
        env_vars = {
            "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_DEPLOYMENT": os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            "AZURE_OPENAI_API_KEY": "***" + (os.getenv("AZURE_OPENAI_API_KEY")[-4:] if os.getenv("AZURE_OPENAI_API_KEY") and len(os.getenv("AZURE_OPENAI_API_KEY")) > 4 else "none"),
            "DATABRICKS_SERVER_HOSTNAME": os.getenv("DATABRICKS_SERVER_HOSTNAME"),
            "DATABRICKS_ACCESS_TOKEN": "***" + (os.getenv("DATABRICKS_ACCESS_TOKEN")[-4:] if os.getenv("DATABRICKS_ACCESS_TOKEN") and len(os.getenv("DATABRICKS_ACCESS_TOKEN")) > 4 else "none"),
            "DATABRICKS_HTTP_PATH": os.getenv("DATABRICKS_HTTP_PATH")
        }
        
        # Check if required vars are set
        required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        return {
            "status": "success",
            "env_file_exists": env_exists,
            "env_file_path": str(env_file),
            "environment_variables": env_vars,
            "missing_required_vars": missing_vars,
            "current_working_directory": os.getcwd()
        }
            
    except Exception as e:
        logger.error(f"Detailed diagnostics failed: {str(e)}")
        return {
            "status": "error",
            "message": "Detailed diagnostic failed",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)