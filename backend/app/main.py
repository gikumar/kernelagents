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

# New imports for the modular structure
from app.core.kernel_setup import create_kernel
from app.core.service_registry import AgentRegistry
from app.core.config_manager import config

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

# Global agent registry
agent_registry = {}

# Request/Response Models
class AskRequest(BaseModel):
    prompt: str
    agentMode: Optional[str] = "Balanced"
    conversation_id: Optional[str] = "default" 

class AskResponse(BaseModel):
    response: str
    status: str
    visualization: Optional[Dict] = None
    has_chart: Optional[bool] = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application lifespan")
    
    # Ensure cache directory exists
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    # PAUSED: Schema loading to avoid costs
    logger.info("⏸️  Schema loading paused to avoid costs - will resume when needed")
    
    try:
        # Create kernel
        kernel = create_kernel()
        
        # Initialize all registered agents
        for agent_name in AgentRegistry.list_agents():
            agent = AgentRegistry.get_agent(agent_name, kernel)
            await agent.initialize()
            agent_registry[agent_name] = agent
            logger.info(f"✅ {agent_name} agent initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize agents: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    
    finally:
        # Cleanup
        for agent_name, agent in agent_registry.items():
            try:
                await agent.cleanup()
                logger.info(f"🧹 {agent_name} agent cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up {agent_name}: {str(e)}")

# Create the FastAPI app with lifespan
app = FastAPI(lifespan=lifespan, title="Azure AI Agent API")

# CORS middleware
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

@app.post("/ask", response_model=AskResponse)
async def ask_agent(request: AskRequest):
    """Endpoint that uses Azure AI Agent for AUTOMATIC function calling"""
    logger.info(f"🚀 Received /ask request: {request.prompt[:100]}...")
    
    try:
        # Use trading agent (which now uses Azure AI Agent for auto-routing)
        trading_agent = agent_registry.get("trading")
        if not trading_agent:
            raise HTTPException(status_code=500, detail="Trading agent not initialized")
        
        # Azure AI Agent will automatically handle function calling
        result = await trading_agent.process_request(request.prompt)
        
        return AskResponse(response=result, status="success", has_chart=False)
        
    except Exception as e:
        logger.error(f"Unexpected error in /ask: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    agents_status = {
        agent_name: "initialized" if agent else "not initialized"
        for agent_name, agent in agent_registry.items()
    }
    
    return {
        "status": "healthy",
        "service": "Azure AI Agent Backend",
        "version": "2.0",
        "features": ["azure_ai_agent", "llm_conversation", "databricks_query", "function_calling"],
        "agents": agents_status,
        "config_status": {
            "azure_openai_configured": config.azure_openai_valid,
            "databricks_configured": config.databricks_valid
        }
    }

@app.get("/diagnostics/detailed")
async def detailed_diagnostics():
    """Detailed diagnostic including environment variables"""
    try:
        # Check if .env file exists
        env_file = Path(__file__).parent.parent / ".env"
        env_exists = env_file.exists()
        
        # Get config summary
        config_summary = config.get_config_summary()
        
        # Check if required vars are set
        required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        return {
            "status": "success",
            "env_file_exists": env_exists,
            "env_file_path": str(env_file),
            "environment_variables": config_summary,
            "missing_required_vars": missing_vars,
            "current_working_directory": os.getcwd(),
            "config_errors": config.errors,
            "config_warnings": config.warnings
        }
            
    except Exception as e:
        logger.error(f"Detailed diagnostics failed: {str(e)}")
        return {
            "status": "error",
            "message": "Detailed diagnostic failed",
            "error": str(e)
        }

@app.get("/agents")
async def list_agents():
    """List all available agents"""
    return {
        "available_agents": AgentRegistry.list_agents(),
        "initialized_agents": list(agent_registry.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)