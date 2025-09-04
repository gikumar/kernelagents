import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

def check_function_calling():
    print("=== Function Calling Capability Check ===")
    
    # Check if required environment variables are set
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    
    if not all([deployment_name, endpoint, api_key]):
        print("❌ Missing required environment variables")
        print(f"Deployment: {deployment_name}")
        print(f"Endpoint: {endpoint}")
        print(f"API Key: {'Set' if api_key else 'Missing'}")
        return
    
    print(f"✅ Environment variables loaded")
    print(f"Deployment: {deployment_name}")
    print(f"Endpoint: {endpoint}")
    
    try:
        from semantic_kernel import Kernel
        from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
        
        # Initialize kernel
        kernel = Kernel()

        # Add Azure Chat Service with correct parameters
        service = AzureChatCompletion(
            service_id="test_function_calling",
            deployment_name=deployment_name,  # Use from environment
            endpoint=endpoint,                # Use from environment
            api_key=api_key,                  # Use from environment
        )
        kernel.add_service(service)
        print("✅ AzureChatCompletion service initialized successfully")

        # Test if function calling is available
        from semantic_kernel.functions import kernel_function

        @kernel_function(name="get_weather", description="Get weather for a location")
        def get_weather(location: str) -> str:
            return f"Weather in {location}: Sunny, 25°C"

        kernel.add_function(plugin_name="weather", function_name="get_weather", function=get_weather)
        print("✅ Function calling setup successful")

        # Check function calling capabilities
        try:
            from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.azure_chat_prompt_execution_settings import (
                AzureChatPromptExecutionSettings,
            )
            print("✅ AzureChatPromptExecutionSettings available")
            
            # Test function choice behaviors
            settings = AzureChatPromptExecutionSettings(
                function_choice_behavior="auto",
                tool_choice="auto"
            )
            print("✅ Function choice behaviors supported")
            
        except ImportError as e:
            print(f"❌ Advanced function calling features: {e}")

    except Exception as e:
        print(f"❌ Function calling setup failed: {e}")
        import traceback
        traceback.print_exc()

    # Check available models and their capabilities
    print("\n=== Model Capabilities ===")
    print("Note: Function calling requires models like gpt-4-1106-preview or later")
    print("Current deployment:", deployment_name)

if __name__ == "__main__":
    check_function_calling()