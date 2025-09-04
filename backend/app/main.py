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
import time

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
    logger.info("⭐ setup_logging() - Entry")
    try:
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
        
        logger.info("⭐ Logging configured successfully")
        
    except Exception as e:
        print(f"💥 Failed to setup logging: {str(e)}")
        raise
    finally:
        logger.info("⭐ setup_logging() - Exit")

# Set up logger first for basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Call this function before creating the FastAPI app
setup_logging()

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
    """Application lifespan management with proper resource handling"""
    logger.info("⭐ lifespan() - Entry")
    startup_time = time.time()
    
    try:
        logger.info("🚀 Starting application lifespan")
        
        # Ensure cache directory exists
        cache_dir = Path(__file__).parent / "cache"
        cache_dir.mkdir(exist_ok=True)
        logger.info(f"⭐ Cache directory ensured: {cache_dir}")
        
        # PAUSED: Schema loading to avoid costs
        logger.info("⏸️  Schema loading paused to avoid costs - will resume when needed")
        
        # Initialize all agents through singleton registry
        from app.core.service_registry import AgentRegistry
        
        logger.info("⭐ Initializing agents through singleton registry")
        
        # Get agents (they will be created as singletons)
        trading_agent = AgentRegistry.get_agent("trading")
        
        # Initialize them
        logger.info("⭐ Initializing TradingAgent")
        await trading_agent.initialize()
        
        # Store in global registry for API access
        agent_registry["trading"] = trading_agent
        
        startup_duration = time.time() - startup_time
        logger.info(f"✅ All agents initialized successfully in {startup_duration:.2f} seconds")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize agents: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    
    finally:
        logger.info("⭐ Starting application cleanup")
        cleanup_time = time.time()
        
        try:
            # Cleanup through singleton registry
            await AgentRegistry.cleanup_all()
            cleanup_duration = time.time() - cleanup_time
            logger.info(f"✅ Application cleanup completed in {cleanup_duration:.2f} seconds")
        except Exception as e:
            logger.error(f"💥 Error during cleanup: {str(e)}")
        finally:
            logger.info("⭐ lifespan() - Exit")

# Create the FastAPI app with lifespan
app = FastAPI(lifespan=lifespan, title="Azure AI Agent API", version="2.0")

# CORS middleware
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
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
    logger.info(f"⭐ ask_agent() - Entry: '{request.prompt[:50]}...'")
    start_time = time.time()
    
    try:
        logger.info(f"🚀 Received /ask request: {request.prompt[:100]}...")
        logger.info(f"⭐ Conversation ID: {request.conversation_id}, Agent Mode: {request.agentMode}")
        
        # Use trading agent (which now uses Azure AI Agent for auto-routing)
        trading_agent = agent_registry.get("trading")
        if not trading_agent:
            error_msg = "Trading agent not initialized"
            logger.error(f"💥 {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Prepare context for the agent
        context = {
            'conversation_id': request.conversation_id,
            'agent_mode': request.agentMode
        }
        
        logger.info("⭐ Processing request with Azure AI Agent")
        
        # Azure AI Agent will automatically handle function calling with context
        result = await trading_agent.process_request(request.prompt, context)
        
        processing_time = time.time() - start_time
        logger.info(f"✅ Request processed successfully in {processing_time:.2f} seconds")
        
        return AskResponse(
            response=result, 
            status="success", 
            has_chart=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_time = time.time() - start_time
        logger.error(f"💥 Unexpected error in /ask after {error_time:.2f}s: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )
    finally:
        logger.info("⭐ ask_agent() - Exit")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("⭐ health_check() - Entry")
    
    try:
        agents_status = {}
        for agent_name, agent in agent_registry.items():
            agents_status[agent_name] = {
                "initialized": agent is not None,
                "type": type(agent).__name__ if agent else "None"
            }
        
        # Get detailed agent status from registry
        detailed_status = AgentRegistry.get_all_agents_status()
        
        health_status = {
            "status": "healthy",
            "service": "Azure AI Agent Backend",
            "version": "2.0",
            "uptime": "unknown",  # Could be enhanced with startup time tracking
            "features": ["azure_ai_agent", "llm_conversation", "databricks_query", "function_calling"],
            "agents": agents_status,
            "detailed_agent_status": detailed_status,
            "config_status": {
                "azure_openai_configured": config.azure_openai_valid,
                "databricks_configured": config.databricks_valid
            }
        }
        
        logger.info("✅ Health check completed successfully")
        return health_status
        
    except Exception as e:
        logger.error(f"💥 Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "error": str(e),
            "service": "Azure AI Agent Backend"
        }
    finally:
        logger.info("⭐ health_check() - Exit")

@app.get("/diagnostics/detailed")
async def detailed_diagnostics():
    """Detailed diagnostic including environment variables"""
    logger.info("⭐ detailed_diagnostics() - Entry")
    
    try:
        # Check if .env file exists
        env_file = Path(__file__).parent.parent / ".env"
        env_exists = env_file.exists()
        
        # Get config summary
        config_summary = config.get_config_summary()
        
        # Check if required vars are set
        required_vars = ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_DEPLOYMENT"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        # Get agent status
        agent_status = AgentRegistry.get_all_agents_status()
        
        diagnostics = {
            "status": "success",
            "timestamp": time.time(),
            "env_file_exists": env_exists,
            "env_file_path": str(env_file),
            "environment_variables": config_summary,
            "missing_required_vars": missing_vars,
            "current_working_directory": os.getcwd(),
            "python_version": sys.version,
            "config_errors": config.errors,
            "config_warnings": config.warnings,
            "agent_status": agent_status,
            "loaded_modules": list(sys.modules.keys())[:20]  # First 20 modules
        }
        
        logger.info("✅ Detailed diagnostics completed successfully")
        return diagnostics
            
    except Exception as e:
        logger.error(f"💥 Detailed diagnostics failed: {str(e)}")
        return {
            "status": "error",
            "message": "Detailed diagnostic failed",
            "error": str(e),
            "timestamp": time.time()
        }
    finally:
        logger.info("⭐ detailed_diagnostics() - Exit")

@app.get("/agents")
async def list_agents():
    """List all available agents"""
    logger.info("⭐ list_agents() - Entry")
    
    try:
        available_agents = AgentRegistry.list_agents()
        initialized_agents = list(agent_registry.keys())
        
        result = {
            "available_agents": available_agents,
            "initialized_agents": initialized_agents,
            "agent_details": {}
        }
        
        # Add details for each agent
        for agent_name in available_agents:
            result["agent_details"][agent_name] = AgentRegistry.get_agent_status(agent_name)
        
        logger.info(f"✅ Agent list retrieved: {len(available_agents)} available, {len(initialized_agents)} initialized")
        return result
        
    except Exception as e:
        logger.error(f"💥 Error listing agents: {str(e)}")
        return {
            "error": str(e),
            "available_agents": [],
            "initialized_agents": []
        }
    finally:
        logger.info("⭐ list_agents() - Exit")

@app.get("/conversations/stats")
async def get_conversation_stats():
    """Get conversation statistics"""
    logger.info("⭐ get_conversation_stats() - Entry")
    
    try:
        trading_agent = agent_registry.get("trading")
        if not trading_agent:
            return {"error": "Trading agent not available"}
        
        if hasattr(trading_agent, 'get_conversation_stats'):
            stats = trading_agent.get_conversation_stats()
            logger.info(f"✅ Conversation stats retrieved: {stats.get('total_conversations', 0)} conversations")
            return stats
        else:
            logger.warning("⭐ Trading agent doesn't have get_conversation_stats method")
            return {"error": "Conversation stats not available"}
            
    except Exception as e:
        logger.error(f"💥 Error getting conversation stats: {str(e)}")
        return {"error": str(e)}
    finally:
        logger.info("⭐ get_conversation_stats() - Exit")

@app.get("/")
async def root():
    """Root endpoint with API information"""
    logger.info("⭐ root() - Entry")
    
    try:
        return {
            "message": "Azure AI Agent API",
            "version": "2.0",
            "endpoints": {
                "health": "/health",
                "ask": "/ask",
                "agents": "/agents",
                "diagnostics": "/diagnostics/detailed",
                "conversation_stats": "/conversations/stats"
            },
            "documentation": "See /docs for API documentation"
        }
    finally:
        logger.info("⭐ root() - Exit")

if __name__ == "__main__":
    logger.info("⭐ Starting application with uvicorn")
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"💥 Failed to start application: {str(e)}")
        raise