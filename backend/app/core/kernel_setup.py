# backend/app/core/kernel_setup.py (simple version)
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from app.core.config_manager import config

def create_kernel() -> Kernel:
    """Create and configure the Semantic Kernel"""
    kernel = Kernel()
    
    # Add Azure OpenAI service
    azure_service = AzureChatCompletion(
        service_id="azure_gpt4o",
        deployment_name=config.AZURE_OPENAI_DEPLOYMENT,
        endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION
    )
    kernel.add_service(azure_service)
    
    return kernel