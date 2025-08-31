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

class AskResponse(BaseModel):
    response: str
    status: str

@app.post("/ask", response_model=AskResponse)
async def ask_agent(request: AskRequest):
    """
    Simple endpoint that uses Semantic Kernel function calling
    """
    logger.info(f"🚀 Received /ask request: {request.prompt[:100]}...")
    
    try:
        # Use the global function_calling_manager instance
        global function_calling_manager
        if function_calling_manager is None:
            raise HTTPException(status_code=500, detail="Function calling manager not initialized")
        
        result = await function_calling_manager.execute_with_function_calling(request.prompt)
        
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

@app.post("/function-calling/execute")
async def execute_function_calling(request: Dict[str, Any]):
    """Execute function calling with the prompt"""
    try:
        # Use the global function_calling_manager instance
        global function_calling_manager
        if function_calling_manager is None:
            return {"error": "Function calling manager not initialized"}
        
        prompt = request.get("prompt", "")
        logger.info(f"🚀 Executing function calling for: {prompt[:100]}...")
        result = await function_calling_manager.execute_with_function_calling(prompt)
        
        return {"result": result}
    except Exception as e:
        logger.error(f"Error in function calling: {str(e)}")
        return {"error": str(e)}

@app.get("/function-calling/capabilities")
async def get_function_capabilities():
    """Get available function calling capabilities"""
    try:
        # Import directly from the module, not the global instance
        from function_calling_manager import AVAILABLE_FUNCTIONS
        from config import DEPLOYMENT_NAME
        
        return {
            "current_deployment": DEPLOYMENT_NAME,
            "available_functions": AVAILABLE_FUNCTIONS,
            "supported": True,
            "model_type": "GPT-4o"
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

@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "AI Agent Backend",
        "version": "1.1",
        "features": ["function_calling", "databricks_query"]
    }

@app.get("/diagnostics/databricks")
async def databricks_diagnostics():
    """Diagnostic endpoint to check Databricks connection"""
    try:
        from function_calling_manager import FunctionCallingManager
        from semantic_kernel import Kernel
        
        kernel = Kernel()
        fc_manager = FunctionCallingManager(kernel)
        
        # Test connection
        connection = fc_manager._get_databricks_connection()
        
        if connection is None:
            return {
                "status": "error",
                "message": "Could not establish Databricks connection",
                "details": "Check your .env file and network connectivity"
            }
        
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
            "DATABRICKS_SERVER_HOSTNAME": os.getenv("DATABRICKS_SERVER_HOSTNAME"),
            "DATABRICKS_ACCESS_TOKEN": "***" + (os.getenv("DATABRICKS_ACCESS_TOKEN")[-4:] if os.getenv("DATABRICKS_ACCESS_TOKEN") and len(os.getenv("DATABRICKS_ACCESS_TOKEN")) > 4 else "none"),
            "DATABRICKS_HTTP_PATH": os.getenv("DATABRICKS_HTTP_PATH"),
            "DATABRICKS_CATALOG": os.getenv("DATABRICKS_CATALOG"),
            "DATABRICKS_SCHEMA": os.getenv("DATABRICKS_SCHEMA")
        }
        
        # Check if required vars are set
        required_vars = ["DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_ACCESS_TOKEN", "DATABRICKS_HTTP_PATH"]
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

@app.get("/diagnostics/connection-test")
async def connection_test():
    """Test Databricks connection with different parameters"""
    try:
        import os
        import databricks.sql
        from databricks.sql.exc import Error
        
        server = os.getenv("DATABRICKS_SERVER_HOSTNAME")
        token = os.getenv("DATABRICKS_ACCESS_TOKEN")
        http_path = os.getenv("DATABRICKS_HTTP_PATH")
        
        if not all([server, token, http_path]):
            return {
                "status": "error",
                "message": "Missing required environment variables",
                "server_provided": bool(server),
                "token_provided": bool(token),
                "http_path_provided": bool(http_path)
            }
        
        # Test 1: Basic connection
        try:
            connection = databricks.sql.connect(
                server_hostname=server,
                http_path=http_path,
                access_token=token
            )
            connection.close()
            basic_connect = "✅ Success"
        except Error as e:
            basic_connect = f"❌ Failed: {str(e)}"
        except Exception as e:
            basic_connect = f"❌ Unexpected error: {str(e)}"
        
        # Test 2: Connection with different parameters
        test_results = {"basic_connection": basic_connect}
        
        # Test with different HTTP path variations
        http_path_variations = [
            http_path,
            http_path.rstrip('/'),
            http_path + '/' if not http_path.endswith('/') else http_path
        ]
        
        for i, path in enumerate(set(http_path_variations)):
            try:
                connection = databricks.sql.connect(
                    server_hostname=server,
                    http_path=path,
                    access_token=token
                )
                connection.close()
                test_results[f"http_path_variation_{i}"] = f"✅ Success with: {path}"
            except Exception as e:
                test_results[f"http_path_variation_{i}"] = f"❌ Failed with {path}: {str(e)}"
        
        return {
            "status": "success",
            "connection_tests": test_results,
            "used_parameters": {
                "server": server,
                "http_path_original": http_path,
                "token_length": len(token) if token else 0
            }
        }
            
    except Exception as e:
        return {
            "status": "error",
            "message": "Connection test failed",
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
    
    # Check numpy (common dependency issue)
    try:
        import numpy
        import_checks["numpy"] = f"✅ Success (version: {numpy.__version__})"
    except Exception as e:
        import_checks["numpy"] = f"❌ Failed: {e}"
    
    # Check other dependencies
    try:
        import semantic_kernel
        import_checks["semantic_kernel"] = "✅ Success"
    except Exception as e:
        import_checks["semantic_kernel"] = f"❌ Failed: {e}"
    
    return {
        "status": "success",
        "import_checks": import_checks
    }


@app.get("/debug/env-check")
async def debug_env_check():
    """Debug endpoint to see what environment variables are available"""
    import os
    from dotenv import load_dotenv
    from pathlib import Path
    
    # Load from correct location
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
    
    return {
        "server": os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        "http_path": os.getenv("DATABRICKS_HTTP_PATH"),
        "token_set": bool(os.getenv("DATABRICKS_ACCESS_TOKEN")),
        "env_file_used": str(env_path),
        "env_file_exists": env_path.exists()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)