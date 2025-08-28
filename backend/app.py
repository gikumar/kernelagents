# app.py - Enhanced with multi-agent management
import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.agents import AzureAIAgent
from azure.ai.projects.aio import AIProjectClient
from azure.identity import DefaultAzureCredential
from typing import Dict, Optional

# Load environment variables
load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_AI_PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
AZURE_AI_AGENT_ID = os.getenv("AZURE_AI_AGENT_ID", None)

if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_KEY or not AZURE_OPENAI_DEPLOYMENT:
    raise ValueError("Please update Azure OpenAI credentials in your .env file.")

if not AZURE_AI_PROJECT_ENDPOINT:
    raise ValueError("Please set AZURE_AI_PROJECT_ENDPOINT in your .env file.")

# Initialize FastAPI with CORS support
app = FastAPI(title="Semantic Kernel API")

# Add CORS middleware to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Kernel
kernel = Kernel()

# Add Azure Chat Service
service_id = "azure_chat_completion"
azure_chat_service = AzureChatCompletion(
    service_id=service_id,
    deployment_name=AZURE_OPENAI_DEPLOYMENT,
    endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
)
kernel.add_service(azure_chat_service)

# Create Azure AI Project client
credential = DefaultAzureCredential()
client = AIProjectClient(
    credential=credential,
    endpoint=AZURE_AI_PROJECT_ENDPOINT,
)

# Agent registry to manage multiple agents
agent_registry: Dict[str, AzureAIAgent] = {}
agent_definitions_cache: Dict[str, dict] = {}

# Pydantic models
class UserPrompt(BaseModel):
    prompt: str
    agent_name: Optional[str] = "default"

class AgentConfig(BaseModel):
    name: str
    description: str
    instructions: str
    model: str = AZURE_OPENAI_DEPLOYMENT

async def find_agent_by_name(agent_name: str):
    """Find an existing agent by name"""
    try:
        async for agent in client.agents.list_agents():
            if agent.name.lower() == agent_name.lower():
                return agent
        return None
    except Exception as e:
        print(f"Error searching for agent: {str(e)}")
        return None

async def get_or_create_agent(agent_config: dict):
    """Get existing agent or create a new one if it doesn't exist"""
    agent_name = agent_config["name"]
    
    # Check if we already have this agent in memory
    if agent_name in agent_registry:
        print(f"Using cached agent: {agent_name}")
        return agent_registry[agent_name]
    
    # Check if agent exists in Azure AI
    existing_agent = await find_agent_by_name(agent_name)
    
    if existing_agent:
        print(f"Found existing agent: {agent_name} (ID: {existing_agent.id})")
        # Initialize AzureAIAgent with the existing agent
        agent = AzureAIAgent(
            definition=existing_agent,
            kernel=kernel,
            client=client
        )
        agent_registry[agent_name] = agent
        agent_definitions_cache[agent_name] = agent_config
        return agent
    else:
        # Create new agent
        print(f"Creating new agent: {agent_name}")
        created_agent = await client.agents.create_agent(body=agent_config)
        print(f"Agent created with ID: {created_agent.id}")

        # Initialize AzureAIAgent
        agent = AzureAIAgent(
            definition=created_agent,
            kernel=kernel,
            client=client
        )
        agent_registry[agent_name] = agent
        agent_definitions_cache[agent_name] = agent_config
        return agent

# Pre-defined agent configurations
DEFAULT_AGENTS = {
    "default": {
        "name": "HelpfulAssistant",
        "description": "A helpful AI assistant",
        "instructions": "You are a helpful AI assistant. Provide clear and concise responses to user queries.",
        "model": AZURE_OPENAI_DEPLOYMENT,
    },
    "creative": {
        "name": "CreativeWriter",
        "description": "A creative writing assistant",
        "instructions": "You are a creative writing assistant. Help users with storytelling, poetry, and creative content generation. Be imaginative and engaging.",
        "model": AZURE_OPENAI_DEPLOYMENT,
    },
    "technical": {
        "name": "TechnicalExpert",
        "description": "A technical expert assistant",
        "instructions": "You are a technical expert. Provide detailed, accurate technical information about programming, cloud services, and software development. Be precise and include code examples when appropriate.",
        "model": AZURE_OPENAI_DEPLOYMENT,
    },
    "analytical": {
        "name": "DataAnalyst",
        "description": "A data analysis assistant",
        "instructions": "You are a data analyst. Help users with data interpretation, statistics, and analytical reasoning. Be logical and methodical in your approach.",
        "model": AZURE_OPENAI_DEPLOYMENT,
    }
}

@app.on_event("startup")
async def startup_event():
    """Initialize agents on startup"""
    print("Initializing agents...")
    
    # Initialize default agent
    try:
        default_agent = await get_or_create_agent(DEFAULT_AGENTS["default"])
        print(f"Default agent initialized: {DEFAULT_AGENTS['default']['name']}")
    except Exception as e:
        print(f"Error initializing default agent: {str(e)}")
        print("Application will continue but agent functionality may be limited")

# Health check endpoint
@app.get("/health")
async def health_check():
    agents_info = []
    for name, agent in agent_registry.items():
        agents_info.append({
            "name": name,
            "initialized": agent is not None,
            "definition": agent_definitions_cache.get(name, {})
        })
    
    return {
        "status": "healthy", 
        "initialized_agents": agents_info,
        "available_agent_types": list(DEFAULT_AGENTS.keys())
    }

# Get available agents
@app.get("/agents")
async def list_agents():
    """List all available agents"""
    return {
        "predefined_agents": list(DEFAULT_AGENTS.keys()),
        "initialized_agents": list(agent_registry.keys()),
        "agent_definitions": agent_definitions_cache
    }

# POST endpoint with agent selection
@app.post("/ask")
async def ask(user_prompt: UserPrompt):
    try:
        agent_name = user_prompt.agent_name or "default"
        
        # Get or create the requested agent
        if agent_name in DEFAULT_AGENTS:
            agent_config = DEFAULT_AGENTS[agent_name]
            agent = await get_or_create_agent(agent_config)
        else:
            # Use default agent if requested agent doesn't exist
            print(f"Agent '{agent_name}' not found. Using default agent.")
            agent_config = DEFAULT_AGENTS["default"]
            agent = await get_or_create_agent(agent_config)
        
        if agent is None:
            return {"error": f"Agent '{agent_name}' not initialized. Check startup logs."}
        
        print(f"Processing prompt with agent '{agent_name}': {user_prompt.prompt}")
        
        # Process the prompt
        response_messages = []
        async for response_chunk in agent.invoke(user_prompt.prompt):
            response_messages.append(str(response_chunk))
        
        full_response = " ".join(response_messages)
        return {
            "response": full_response,
            "agent_used": agent_name,
            "agent_description": agent_config["description"]
        }
        
    except Exception as e:
        print(f"Error in ask endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "type": type(e).__name__}

# Create custom agent endpoint
@app.post("/agents/create")
async def create_custom_agent(agent_config: AgentConfig):
    """Create a custom agent with specific configuration"""
    try:
        # Check if agent already exists
        existing_agent = await find_agent_by_name(agent_config.name)
        if existing_agent:
            return {
                "message": f"Agent '{agent_config.name}' already exists",
                "agent_id": existing_agent.id,
                "status": "existing"
            }
        
        # Create new agent
        config_dict = agent_config.dict()
        agent = await get_or_create_agent(config_dict)
        
        return {
            "message": f"Agent '{agent_config.name}' created successfully",
            "agent_name": agent_config.name,
            "status": "created"
        }
        
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

# Alternative: Direct kernel invocation (fallback)
@app.post("/ask-direct")
async def ask_direct(user_prompt: UserPrompt):
    try:
        prompt_template = """
        You are a helpful AI assistant. Please respond to the user's query.

        User: {{$input}}
        Assistant:
        """
        
        function = kernel.add_function(
            plugin_name="AssistantPlugin",
            function_name="Respond",
            prompt=prompt_template,
        )
        
        result = await kernel.invoke(function, input=user_prompt.prompt)
        return {"response": str(result)}
        
    except Exception as e:
        return {"error": str(e)}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Semantic Kernel API running",
        "endpoints": {
            "health_check": "/health",
            "list_agents": "/agents (GET)",
            "ask_agent": "/ask (POST)",
            "create_agent": "/agents/create (POST)",
            "ask_direct": "/ask-direct (POST)"
        },
        "available_agents": list(DEFAULT_AGENTS.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)