# function_calling_manager.py - Complete implementation for GPT-4o
import os
from typing import List, Dict, Optional, Any
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
    AzureChatPromptExecutionSettings,
)
from semantic_kernel.functions import kernel_function

class FunctionCallingManager:
    """
    Complete function calling manager with parallel calls and choice behaviors
    for GPT-4o and other supported models.
    """
    
    def __init__(self, kernel: Kernel):
        self.kernel = kernel
        self.functions_registered = False
        print("✅ Function Calling Manager initialized for GPT-4o")
    
    @kernel_function(name="get_weather", description="Get weather for a specific location")
    def get_weather(self, location: str) -> str:
        """Get weather information for a specific location"""
        # Simulated weather data - in real app, call a weather API
        weather_data = {
            "new york": "Sunny, 25°C, Light breeze",
            "london": "Cloudy, 18°C, Light rain",
            "tokyo": "Clear, 28°C, Humid", 
            "san francisco": "Foggy, 20°C, Moderate wind"
        }
        return f"Weather in {location}: {weather_data.get(location.lower(), 'Sunny, 24°C')}"
    
    @kernel_function(name="get_stock_price", description="Get current stock price for a symbol")
    def get_stock_price(self, symbol: str) -> str:
        """Get stock price for a symbol"""
        # Simulated stock data
        stock_data = {
            "AAPL": "$185.32 ↗️ (+1.5%)",
            "MSFT": "$412.56 ↗️ (+2.3%)", 
            "GOOGL": "$172.45 ↘️ (-0.8%)",
            "TSLA": "$245.78 ↗️ (+3.2%)"
        }
        return f"Stock {symbol}: {stock_data.get(symbol.upper(), '$150.00 → (0.0%)')}"
    
    @kernel_function(name="calculate_business_metrics", description="Calculate various business metrics")
    def calculate_business_metrics(self, metric_type: str, period: str = "monthly") -> str:
        """Calculate business metrics"""
        metrics = {
            "revenue": {"monthly": "$1.2M", "quarterly": "$3.8M", "yearly": "$14.5M"},
            "growth": {"monthly": "15%", "quarterly": "22%", "yearly": "45%"},
            "profit": {"monthly": "$450K", "quarterly": "$1.4M", "yearly": "$5.2M"}
        }
        
        result = metrics.get(metric_type.lower(), {}).get(period.lower(), "Data not available")
        return f"{metric_type} metrics for {period}: {result}"
    
    @kernel_function(name="analyze_sentiment", description="Analyze sentiment of text")
    def analyze_sentiment(self, text: str) -> str:
        """Analyze sentiment of given text"""
        # Simple sentiment analysis - in real app, use proper NLP
        positive_words = ["love", "great", "excellent", "amazing", "happy", "good", "wonderful"]
        negative_words = ["hate", "terrible", "awful", "bad", "sad", "angry", "disappointing"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "Sentiment: Positive 😊 (Score: 0.85)"
        elif negative_count > positive_count:
            return "Sentiment: Negative 😞 (Score: 0.25)" 
        else:
            return "Sentiment: Neutral 😐 (Score: 0.50)"
    
    @kernel_function(name="get_news_summary", description="Get news summary for a topic")
    def get_news_summary(self, topic: str) -> str:
        """Get news summary for a topic"""
        news_topics = {
            "technology": "AI advancements accelerating across industries. New GPT models released.",
            "finance": "Markets show resilience amid economic shifts. Interest rates stable.",
            "sports": "Championship season underway with exciting matches and record performances."
        }
        return f"News about {topic}: {news_topics.get(topic.lower(), 'Latest updates available')}"
    
    def register_functions(self):
        """Register all functions with the kernel"""
        # Add functions to kernel with proper plugins
        self.kernel.add_function(plugin_name="weather_service", function_name="get_weather", function=self.get_weather)
        self.kernel.add_function(plugin_name="finance_service", function_name="get_stock_price", function=self.get_stock_price)
        self.kernel.add_function(plugin_name="business_analytics", function_name="calculate_business_metrics", function=self.calculate_business_metrics)
        self.kernel.add_function(plugin_name="text_analysis", function_name="analyze_sentiment", function=self.analyze_sentiment)
        self.kernel.add_function(plugin_name="news_service", function_name="get_news_summary", function=self.get_news_summary)
        
        self.functions_registered = True
        print("✅ All functions registered for parallel calling")
    
    async def execute_with_function_calling(self, prompt: str, 
                                          function_choice_behavior: str = "auto",
                                          max_tokens: int = 2000):
        """
        Execute with parallel function calling and choice behaviors
        """
        if not self.functions_registered:
            self.register_functions()
        
        # Configure execution settings for advanced function calling
        execution_settings = AzureChatPromptExecutionSettings(
            service_id="azure_chat_completion",
            temperature=0.1,  # Lower temperature for more deterministic function calling
            max_tokens=max_tokens,
            function_choice_behavior=function_choice_behavior,
            tool_choice="auto",  # Enable automatic function calling
        )
        
        try:
            # Invoke with function calling enabled
            result = await self.kernel.invoke(
                function_name="chat",
                plugin_name="chat",
                input=prompt,
                execution_settings=execution_settings
            )
            
            return str(result)
            
        except Exception as e:
            return f"Error in function calling: {str(e)}"
    
    async def parallel_function_demo(self):
        """
        Demo parallel function calling capabilities with GPT-4o
        """
        demo_prompt = """
        Please help me with a comprehensive analysis:
        
        1. Get weather for New York, London, and Tokyo
        2. Check stock prices for AAPL, MSFT, and TSLA
        3. Calculate revenue and growth metrics for quarterly period
        4. Analyze sentiment of these reviews:
           - "I absolutely love this product! The quality is amazing."
           - "The service was terrible and the delivery was late."
        5. Get news summary for technology and finance
        
        Provide a consolidated report with all insights.
        """
        
        return await self.execute_with_function_calling(
            demo_prompt,
            function_choice_behavior="auto",
            max_tokens=3000
        )

# Function choice behavior options
FUNCTION_CHOICE_BEHAVIORS = {
    "auto": "Let the model decide whether to call functions (default)",
    "required": "Force the model to call functions", 
    "none": "Don't allow function calling",
}

# Supported models for advanced function calling
FUNCTION_CALLING_MODELS = [
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4-1106-preview",
    "gpt-4-0125-preview", 
    "gpt-4-turbo-preview",
    "gpt-35-turbo-1106",
]

# Available functions
AVAILABLE_FUNCTIONS = [
    "get_weather", "get_stock_price", "calculate_business_metrics", 
    "analyze_sentiment", "get_news_summary"
]