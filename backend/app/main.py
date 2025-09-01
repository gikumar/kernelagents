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

from dotenv import load_dotenv
from pathlib import Path

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

# Load .env from the backend directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"✅ Loaded .env from: {env_path}")

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global variable for function calling manager
function_calling_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application lifespan")
    
    # Ensure cache directory exists
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    # Load schema at startup - auto-refresh if not found
    try:
        from schema_utils import load_schema
        schema_data = load_schema()  # This will auto-refresh if cache doesn't exist
        
        if not schema_data:
            logger.warning("❌ Failed to load schema automatically")
        else:
            logger.info(f"✅ Schema loaded with {len(schema_data)} tables")
    except Exception as e:
        logger.error(f"❌ Failed to load schema: {str(e)}")
    
    # Initialize function calling manager
    try:
        from function_calling_manager import FunctionCallingManager
        from semantic_kernel import Kernel
        
        kernel = Kernel()
        global function_calling_manager
        function_calling_manager = FunctionCallingManager(kernel)
        function_calling_manager.register_functions()
        logger.info("✅ Function calling manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize function calling manager: {str(e)}")
    
    yield
    logger.info("🚀 Application shutdown")

# Create the FastAPI app with lifespan
app = FastAPI(lifespan=lifespan, title="Semantic Kernel API")

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

@app.post("/ask", response_model=AskResponse)
async def ask_agent(request: AskRequest):
    """
    Intelligent endpoint that routes to LLM or Databricks based on content
    """
    logger.info(f"🚀 Received /ask request: {request.prompt[:100]}...")
    
    try:
        global function_calling_manager
        if function_calling_manager is None:
            raise HTTPException(status_code=500, detail="Function calling manager not initialized")
        
        result = await function_calling_manager.execute_with_function_calling(
            request.prompt, 
            request.conversation_id
        )
        return AskResponse(
            response=result,
            status="success"
        )

    except Exception as e:
        logger.error(f"Unexpected error in /ask: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Add a new endpoint for explicit LLM-only requests
@app.post("/ask/llm", response_model=AskResponse)
async def ask_llm_only(request: AskRequest):
    """Force request to be handled by LLM only"""
    try:
        global function_calling_manager
        if function_calling_manager is None:
            raise HTTPException(status_code=500, detail="Function calling manager not initialized")
        
        result = await function_calling_manager.handle_llm_only(request.prompt, request.conversation_id)
        return AskResponse(response=result, status="success")
        
    except Exception as e:
        logger.error(f"Error in /ask/llm: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add a new endpoint for explicit data queries
@app.post("/ask/data", response_model=AskResponse)
async def ask_data_only(request: AskRequest):
    """Force request to be handled as data query"""
    try:
        global function_calling_manager
        if function_calling_manager is None:
            raise HTTPException(status_code=500, detail="Function calling manager not initialized")
        
        result = await function_calling_manager.handle_databricks_only(request.prompt, request.conversation_id)
        return AskResponse(response=result, status="success")
        
    except Exception as e:
        logger.error(f"Error in /ask/data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    try:
        global function_calling_manager
        if function_calling_manager is None:
            return {"error": "Function calling manager not initialized"}
        
        conversation = function_calling_manager._get_conversation_context(conversation_id)
        return {
            "conversation_id": conversation_id,
            "messages": conversation.get("messages", []),
            "message_count": len(conversation.get("messages", []))
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/function-calling/execute")
async def execute_function_calling(request: Dict[str, Any]):
    """Execute function calling with the prompt"""
    try:
        global function_calling_manager
        if function_calling_manager is None:
            return {"error": "Function calling manager not initialized"}
        
        prompt = request.get("prompt", "")
        conversation_id = request.get("conversation_id", "default")
        logger.info(f"🚀 Executing function calling for: {prompt[:100]}...")
        result = await function_calling_manager.execute_with_function_calling(prompt, conversation_id)
        
        return {"result": result}
    except Exception as e:
        logger.error(f"Error in function calling: {str(e)}")
        return {"error": str(e)}

@app.get("/function-calling/capabilities")
async def get_function_capabilities():
    """Get available function calling capabilities"""
    try:
        from function_calling_manager import AVAILABLE_FUNCTIONS
        from config import AZURE_OPENAI_DEPLOYMENT
        
        return {
            "current_deployment": AZURE_OPENAI_DEPLOYMENT,
            "available_functions": AVAILABLE_FUNCTIONS,
            "supported": True,
            "model_type": "GPT-4o",
            "features": ["intelligent_routing", "databricks_integration", "llm_conversation"]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/schema/refresh")
async def refresh_schema():
    """Refresh schema from Databricks"""
    try:
        from schema_utils import refresh_schema
        schema_data = refresh_schema()
        return {"status": "success", "tables_count": len(schema_data)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health/llm")
async def health_check_llm():
    """Check LLM health status"""
    try:
        global function_calling_manager
        if function_calling_manager is None:
            return {"status": "error", "message": "Function calling manager not initialized"}
        
        if function_calling_manager.llm_manager is None:
            return {"status": "error", "message": "LLM manager not available"}
        
        # Test LLM with a simple prompt
        test_prompt = "Hello, are you working?"
        response = await function_calling_manager.llm_manager.generate_response(test_prompt)
        
        return {
            "status": "success", 
            "message": "LLM is working",
            "test_response": response[:100] + "..." if len(response) > 100 else response
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health/databricks")
async def health_check_databricks():
    """Check Databricks health status"""
    try:
        global function_calling_manager
        if function_calling_manager is None:
            return {"status": "error", "message": "Function calling manager not initialized"}
        
        # Test Databricks connection
        connection = function_calling_manager._get_databricks_connection()
        
        if connection is None:
            return {"status": "error", "message": "Could not establish Databricks connection"}
        
        # Test a simple query
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 as test_value")
                result = cursor.fetchone()
                connection.close()
                
                return {
                    "status": "success", 
                    "message": "Databricks connection successful",
                    "test_query_result": result[0] if result else "no result"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": "Connection established but query failed",
                "error": str(e)
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": "Diagnostic failed",
            "error": str(e)
        }

@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "AI Agent Backend with Intelligent Routing",
        "version": "2.0",
        "features": ["intelligent_routing", "llm_conversation", "databricks_query", "function_calling"]
    }

@app.get("/diagnostics/detailed")
async def detailed_diagnostics():
    """Detailed diagnostic including environment variables"""
    try:
        # Check if .env file exists
        from pathlib import Path
        env_file = Path(__file__).parent / ".env"
        env_exists = env_file.exists()
        
        # Check actual environment variables
        import os
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
        return {
            "status": "error",
            "message": "Detailed diagnostic failed",
            "error": str(e)
        }

@app.get("/diagnostics/imports")
async def import_diagnostics():
    """Check if required packages can be imported"""
    import_checks = {}
    
    # Check databricks-sql
    try:
        import databricks.sql
        import_checks["databricks.sql"] = "✅ Success"
    except ImportError as e:
        import_checks["databricks.sql"] = f"❌ Import failed: {e}"
    except Exception as e:
        import_checks["databricks.sql"] = f"❌ Unexpected error: {e}"
    
    # Check semantic_kernel
    try:
        import semantic_kernel
        import_checks["semantic_kernel"] = f"✅ Success (version: {semantic_kernel.__version__})"
    except Exception as e:
        import_checks["semantic_kernel"] = f"❌ Failed: {e}"
    
    # Check openai
    try:
        import openai
        import_checks["openai"] = f"✅ Success (version: {openai.__version__})"
    except Exception as e:
        import_checks["openai"] = f"❌ Failed: {e}"
    
    return {
        "status": "success",
        "import_checks": import_checks
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)