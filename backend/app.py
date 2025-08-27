# app.py - Backend API with CORS support
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
    allow_origins=["http://localhost:3000"],  # React default port
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

# Azure AI Agent instance
azure_ai_agent = None

# Pydantic model
class UserPrompt(BaseModel):
    prompt: str

@app.on_event("startup")
async def startup_event():
    """Initialize the Azure AI Agent on startup"""
    global azure_ai_agent
    
    try:
        if AZURE_AI_AGENT_ID:
            # Use existing agent
            print(f"Using existing agent with ID: {AZURE_AI_AGENT_ID}")
            
            # Get the agent definition from Azure AI
            agent_definition = await client.agents.get_agent(AZURE_AI_AGENT_ID)
            
            # Initialize AzureAIAgent with the correct parameters
            azure_ai_agent = AzureAIAgent(
                definition=agent_definition,
                kernel=kernel,
                client=client
            )
            print("Azure AI Agent initialized with existing agent")
            
        else:
            # Create new agent with minimal required parameters
            print("Creating new Azure AI Agent...")
            
            # Create agent definition with only valid parameters
            agent_config = {
                "name": "HelpfulAssistant",
                "description": "A helpful AI assistant",
                "instructions": "You are a helpful AI assistant. Provide clear and concise responses to user queries.",
                "model": AZURE_OPENAI_DEPLOYMENT,
            }
            
            # Create the agent using the client
            created_agent = await client.agents.create_agent(body=agent_config)
            print(f"Agent created with ID: {created_agent.id}")

            # Initialize AzureAIAgent with the created agent
            azure_ai_agent = AzureAIAgent(
                definition=created_agent,
                kernel=kernel,
                client=client
            )
            print("Azure AI Agent initialized successfully")
            
    except Exception as e:
        print(f"Error initializing Azure AI Agent: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()


# Helper function to list agents (for debugging)
async def list_agents():
    """List all available agents for debugging"""
    try:
        agents_list = []
        async for agent in client.agents.list_agents():
            agents_list.append({"id": agent.id, "name": agent.name})
        return agents_list
    except Exception as e:
        return f"Error listing agents: {str(e)}"

# Health check endpoint
@app.get("/health")
async def health_check():
    agents_info = await list_agents()
    return {
        "status": "healthy", 
        "agent_initialized": azure_ai_agent is not None,
        "agent_id": AZURE_AI_AGENT_ID or "Not set",
        "available_agents": agents_info
    }

# POST endpoint using Azure AI Agent - CORRECTED ASYNC GENERATOR HANDLING
@app.post("/ask")
async def ask(user_prompt: UserPrompt):
    try:
        if azure_ai_agent is None:
            return {"error": "Azure AI Agent not initialized. Check startup logs."}
        
        print(f"Processing prompt: {user_prompt.prompt}")
        
        # CORRECT: Handle the async generator properly
        response_messages = []
        async for response_chunk in azure_ai_agent.invoke(user_prompt.prompt):
            # Collect each response chunk
            response_messages.append(str(response_chunk))
        
        # Combine all response chunks
        full_response = " ".join(response_messages)
        return {"response": full_response}
        
    except Exception as e:
        print(f"Error in ask endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "type": type(e).__name__}

# Alternative: Use get_response() method for simpler interaction
@app.post("/ask-simple")
async def ask_simple(user_prompt: UserPrompt):
    try:
        if azure_ai_agent is None:
            return {"error": "Azure AI Agent not initialized"}
        
        # Use get_response() which returns a single response
        response = await azure_ai_agent.get_response(user_prompt.prompt)
        return {"response": str(response)}
        
    except Exception as e:
        return {"error": str(e)}

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
            "ask_agent": "/ask (POST)",
            "ask_simple": "/ask-simple (POST)",
            "ask_direct": "/ask-direct (POST)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)