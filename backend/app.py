# backend/app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
from contextlib import asynccontextmanager
import logging
from .agentfactory import AgentFactory
from .utility.thread_cleanup_scheduler import start_thread_cleanup_scheduler

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler with higher level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

sys.path.append(os.path.dirname(__file__))
agent_factory = AgentFactory()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀Starting application lifespan")
    
    # Ensure cache directory exists
    from pathlib import Path
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    # Load schema at startup
    try:
        from .schema_utils import load_schema, refresh_schema
        schema_data = load_schema()
        
        if not schema_data:
            logger.warning("❌ No schema found in cache, refreshing from Databricks...")
            schema_data = refresh_schema()
        
        logger.info(f"✅ Schema loaded with {len(schema_data)} tables")
    except Exception as e:
        logger.error(f"❌ Failed to load schema: {str(e)}")
    
    # Initialize function calling manager
    from .app.function_calling_manager import FunctionCallingManager
    from semantic_kernel import Kernel
    
    kernel = Kernel()
    global function_calling_manager
    function_calling_manager = FunctionCallingManager(kernel)
    function_calling_manager.register_functions()
    
    start_thread_cleanup_scheduler()
    yield
    logger.info("🚀Application shutdown")

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

class Message(BaseModel):
    role: str
    content: str
    isError: Optional[bool] = False

class AskRequest(BaseModel):
    agentMode: str
    prompt: str
    file_content: Optional[str] = None
    chat_history: Optional[List[Message]] = None

class AskResponse(BaseModel):
    response: str
    thread_id: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    graph_data: Optional[Dict[str, Any]] = None
    status: str

@app.post("/ask", response_model=AskResponse)
async def ask_agent(request: AskRequest):
    logger.info("🚀Received /ask request")
    try:
        if not request.prompt and not request.file_content:
            logger.warning("Empty request received")
            raise HTTPException(
                status_code=400,
                detail="Either prompt or file content must be provided"
            )

        formatted_history = None
        if request.chat_history:
            logger.debug(f"Processing chat history with {len(request.chat_history)} messages")
            formatted_history = [
                {
                    "role": msg.role,
                    "content": msg.content
                } 
                for msg in request.chat_history
            ]

        logger.debug(f"Processing request with mode: {request.agentMode}")
        response = agent_factory.process_request2(
            prompt=request.prompt,
            agent_mode=request.agentMode,
            file_content=request.file_content,
            chat_history=formatted_history
        )
        
        logger.info("🚀Request processed successfully")
        return {
            "response": response.response,
            "thread_id": response.thread_id,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "graph_data": response.graph_data,
            "status": "success"
        }

    except HTTPException as http_err:
        logger.error(f"HTTP error in /ask: {http_err.detail}")
        raise http_err
        
    except Exception as e:
        logger.error(f"Unexpected error in /ask: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/function-calling/execute")
async def execute_function_calling(request: Dict[str, Any]):
    """Execute function calling with the prompt"""
    try:
        from .app.function_calling_manager import function_calling_manager
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
    from .app.function_calling_manager import AVAILABLE_FUNCTIONS
    from .config import DEPLOYMENT_NAME
    
    return {
        "current_deployment": DEPLOYMENT_NAME,
        "available_functions": AVAILABLE_FUNCTIONS,
        "supported": True,
        "model_type": "GPT-4o"
    }

@app.get("/schema/refresh")
async def refresh_schema():
    """Refresh schema from Databricks"""
    try:
        from .schema_utils import refresh_schema
        schema_data = refresh_schema()
        return {"status": "success", "tables_count": len(schema_data)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def health_check():
    logger.debug("Health check endpoint called")
    return {
        "status": "healthy",
        "service": "AI Agent Backend",
        "version": "1.1",
        "features": ["text", "graph_generation", "nl_to_sql", "function_calling"]
    }

# Add this for direct execution support
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)