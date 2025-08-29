# app.py - Fixed version with proper function invocation
import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.functions import kernel_function
from typing import Dict, Optional, List

# Load environment variables
load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
ENDPOINTS_KEY = os.getenv("ENDPOINTS_KEY")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME")

if not AZURE_OPENAI_ENDPOINT or not ENDPOINTS_KEY or not DEPLOYMENT_NAME:
    raise ValueError("Please update Azure OpenAI credentials in your .env file.")

# Initialize FastAPI with CORS support
app = FastAPI(title="Semantic Kernel API")

# Add CORS middleware
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
    deployment_name=DEPLOYMENT_NAME,
    endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=ENDPOINTS_KEY,
)
kernel.add_service(azure_chat_service)

# Pydantic models
class UserPrompt(BaseModel):
    prompt: str

class FunctionCallRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 2000

# Create a chat function
def create_chat_function():
    """Create a chat function for the kernel"""
    from semantic_kernel.prompt_template import PromptTemplateConfig
    
    prompt_template = """
    You are a helpful AI assistant. Please respond to the user's query in a helpful and friendly manner.

    User: {{$input}}
    Assistant:
    """
    
    return kernel.add_function(
        function_name="chat",
        plugin_name="assistant",
        prompt=prompt_template,
        description="Chat with the AI assistant"
    )

# Function Calling Manager
class FunctionCallingManager:
    """Function calling manager"""
    
    def __init__(self, kernel: Kernel):
        self.kernel = kernel
        self.functions_registered = False
        print("✅ Function Calling Manager initialized")
    
    def register_functions(self):
        """Register functions with the kernel"""
        from semantic_kernel.functions import kernel_function
        
        @kernel_function(name="get_weather", description="Get weather for a location")
        def get_weather(location: str) -> str:
            weather_data = {
                "new york": "Sunny, 25°C, Light breeze",
                "london": "Cloudy, 18°C, Light rain",
                "tokyo": "Clear, 28°C, Humid", 
                "san francisco": "Foggy, 20°C, Moderate wind",
                "paris": "Partly cloudy, 22°C, Gentle breeze",
                "dubai": "Hot and sunny, 38°C, Dry"
            }
            return f"Weather in {location}: {weather_data.get(location.lower(), 'Sunny, 24°C')}"
        
        @kernel_function(name="get_stock_price", description="Get current stock price")
        def get_stock_price(symbol: str) -> str:
            stock_data = {
                "AAPL": "$185.32 ↗️ (+1.5%)",
                "MSFT": "$412.56 ↗️ (+2.3%)", 
                "GOOGL": "$172.45 ↘️ (-0.8%)",
                "TSLA": "$245.78 ↗️ (+3.2%)",
                "AMZN": "$178.90 ↗️ (+1.2%)",
                "NVDA": "$950.60 ↗️ (+4.1%)"
            }
            return f"Stock {symbol}: {stock_data.get(symbol.upper(), '$150.00 → (0.0%)')}"
        
        @kernel_function(name="analyze_sentiment", description="Analyze text sentiment")
        def analyze_sentiment(text: str) -> str:
            positive_words = ["love", "great", "excellent", "amazing", "happy", "good", "wonderful", "fantastic", "perfect"]
            negative_words = ["hate", "terrible", "awful", "bad", "sad", "angry", "disappointing", "poor", "horrible"]
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count > negative_count:
                return "Sentiment: Positive 😊 (Score: 0.85)"
            elif negative_count > positive_count:
                return "Sentiment: Negative 😞 (Score: 0.25)" 
            else:
                return "Sentiment: Neutral 😐 (Score: 0.50)"
        
        # Add functions to kernel
        self.kernel.add_function(plugin_name="weather_service", function_name="get_weather", function=get_weather)
        self.kernel.add_function(plugin_name="finance_service", function_name="get_stock_price", function=get_stock_price)
        self.kernel.add_function(plugin_name="text_analysis", function_name="analyze_sentiment", function=analyze_sentiment)
        
        self.functions_registered = True
        print("✅ Functions registered")
    
    async def execute_with_function_calling(self, prompt: str, max_tokens: int = 2000):
        """Execute with function calling"""
        if not self.functions_registered:
            self.register_functions()
        
        try:
            # Create a more specific prompt that encourages function calling
            enhanced_prompt = f"""
            Please use the available functions to answer this query. 
            The functions provide simulated data for demonstration purposes.
            
            Query: {prompt}
            
            Please call the appropriate functions to get the information.
            """
            
            # For function calling, we'll use the Azure service directly
            from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
                AzureChatPromptExecutionSettings,
            )
            
            execution_settings = AzureChatPromptExecutionSettings(
                service_id="azure_chat_completion",
                temperature=0.1,
                max_tokens=max_tokens,
                tool_choice="auto",
            )
            
            # Create a temporary function for this invocation
            function = self.kernel.add_function(
                plugin_name="temp_assistant",
                function_name="assist_with_functions",
                prompt=enhanced_prompt,
                description="Assistant that uses available functions"
            )
            
            result = await self.kernel.invoke(
                function=function,
                execution_settings=execution_settings
            )
            
            return str(result)
            
        except Exception as e:
            return f"Error in function calling: {str(e)}"

# Create chat function
chat_function = create_chat_function()

# Initialize function calling manager
function_calling_manager = FunctionCallingManager(kernel)

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("✅ Application started successfully")
    print(f"Using model: {DEPLOYMENT_NAME}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "model": DEPLOYMENT_NAME,
        "function_calling_available": True,
        "service": "Azure OpenAI"
    }

# Basic chat endpoint - FIXED
@app.post("/chat")
async def chat(user_prompt: UserPrompt):
    try:
        # Use the pre-created chat function
        result = await kernel.invoke(
            function=chat_function,
            input=user_prompt.prompt
        )
        return {"response": str(result)}
    except Exception as e:
        return {"error": str(e)}

# Function calling endpoint
@app.post("/function-calling/execute")
async def execute_function_calling(request: FunctionCallRequest):
    try:
        result = await function_calling_manager.execute_with_function_calling(
            request.prompt,
            request.max_tokens
        )
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

# Function calling demo
@app.post("/function-calling/demo")
async def function_calling_demo():
    demo_prompt = "What's the weather in Tokyo and New York? Also show me AAPL stock price and analyze sentiment of 'I love this product!'"
    try:
        result = await function_calling_manager.execute_with_function_calling(demo_prompt)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

# Get capabilities
@app.get("/function-calling/capabilities")
async def get_function_capabilities():
    return {
        "current_deployment": DEPLOYMENT_NAME,
        "available_functions": ["get_weather", "get_stock_price", "analyze_sentiment"],
        "supported": True,
        "model_type": "GPT-4o"
    }

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Semantic Kernel API running",
        "endpoints": {
            "health_check": "/health",
            "chat": "/chat (POST)",
            "function_calling_execute": "/function-calling/execute (POST)",
            "function_calling_demo": "/function-calling/demo (POST)",
            "function_capabilities": "/function-calling/capabilities (GET)"
        },
        "model": DEPLOYMENT_NAME
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)