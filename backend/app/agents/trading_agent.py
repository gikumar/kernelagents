from .base_agent import BaseAgent
from app.plugins.trading_plugin import TradingPlugin
from app.plugins.email_plugin import EmailPlugin
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
from azure.identity import DefaultAzureCredential

class TradingAgent(BaseAgent):
    def __init__(self, kernel):
        super().__init__(kernel, "trading_agent", "Handles trading data and analysis")
        self.azure_agent = None
    
    async def initialize(self):
        """Initialize trading agent with Azure AI Agent for automatic function calling"""
        # Initialize plugins
        self.trading_plugin = TradingPlugin(self.kernel)
        await self.trading_plugin.initialize()
        self.add_plugin(self.trading_plugin)
        
        self.email_plugin = EmailPlugin(self.kernel)
        await self.email_plugin.initialize()
        self.add_plugin(self.email_plugin)
        
        # Create Azure AI Agent for automatic function calling
        await self._create_azure_ai_agent()
    
    async def _create_azure_ai_agent(self):
        """Create Azure AI Agent that handles automatic function calling"""
        
        from app.core.config_manager import config

        credential = DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True
        )
        
        project_client = AzureAIAgent.create_client(credential=credential)
        
        # Define agent with instructions for automatic function calling
        agent_def = await project_client.agents.create_agent(
            model=config.AZURE_OPENAI_DEPLOYMENT,  # Use your model name
            name="trading_assistant",
            instructions="""You are an AI assistant for trading and financial data analysis.
            You can help users query trade data, explain trading concepts, 
            execute custom SQL queries, and provide general trading assistance.
            Use the available plugin functions automatically when appropriate."""
        )
        
        # Create Azure AI Agent that will handle automatic function calling
        self.azure_agent = AzureAIAgent(
            client=project_client,
            definition=agent_def,
            plugins=[self.trading_plugin, self.email_plugin]  # Let Azure AI handle routing
        )
    
    async def process_request(self, prompt: str, context: dict = None):
        """Let Azure AI Agent handle automatic function calling"""
        if not self.azure_agent:
            raise ValueError("Azure AI Agent not initialized")
        
        # Azure AI Agent will automatically decide which functions to call
        response = await self.azure_agent.get_response([prompt])
        return str(response)