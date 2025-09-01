# backend/app/llm_manager.py
import logging
from typing import Dict, List, Optional
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.contents import ChatHistory
from semantic_kernel.prompt_template import PromptTemplateConfig
import json

logger = logging.getLogger(__name__)

class LLMManager:
    """Manager for handling LLM interactions with Azure OpenAI"""
    
    def __init__(self, kernel: Kernel):
        self.kernel = kernel
        self.chat_service = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize Azure OpenAI connection"""
        try:
            from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT
            
            self.chat_service = AzureChatCompletion(
                service_id="azure_gpt4o",
                deployment_name=AZURE_OPENAI_DEPLOYMENT,
                endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_KEY,
                api_version="2024-02-15-preview"
            )
            
            self.kernel.add_service(self.chat_service)
            logger.info("✅ Azure OpenAI GPT-4o initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Azure OpenAI: {str(e)}")
            raise
    
    async def generate_response(self, prompt: str, conversation_history: Optional[ChatHistory] = None) -> str:
        """Generate response using GPT-4o"""
        if not self.chat_service:
            return "LLM service not available. Please check configuration."
        
        try:
            # Create or use existing chat history
            if conversation_history is None:
                conversation_history = ChatHistory()
                # Add system message
                conversation_history.add_system_message("""
                You are a helpful AI assistant for trade data analysis. You can help users with:
                1. General questions and conversations
                2. Data analysis queries (which will be routed to Databricks)
                3. Explaining trade data concepts
                
                Be concise, helpful, and professional.
                """)
            
            # Add user message
            conversation_history.add_user_message(prompt)
            
            # Generate response
            response = await self.kernel.invoke(
                self.chat_service,
                conversation_history=conversation_history
            )
            
            return str(response)
            
        except Exception as e:
            logger.error(f"❌ Error generating LLM response: {str(e)}")
            return f"I apologize, but I encountered an error: {str(e)}"
    
    async def is_data_query(self, prompt: str) -> bool:
        """Determine if the prompt is a data query that should go to Databricks"""
        data_keywords = [
            "data", "query", "select", "show", "get", "list", "find", 
            "trade", "pnl", "profit", "loss", "amount", "volume",
            "record", "row", "table", "database", "databricks",
            "how many", "what is the", "summary", "report", "analysis"
        ]
        
        prompt_lower = prompt.lower()
        
        # Check for explicit data query patterns
        if any(keyword in prompt_lower for keyword in data_keywords):
            return True
        
        # Check for SQL-like patterns
        sql_patterns = ["from", "where", "join", "group by", "order by", "limit"]
        if any(pattern in prompt_lower for pattern in sql_patterns):
            return True
        
        return False