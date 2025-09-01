# backend/test_sql_fix.py
from app.sql_generator import SQLGenerator
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

async def test_sql_fix():
    # Initialize kernel with Azure OpenAI service
    kernel = Kernel()
    
    # Add Azure OpenAI service to kernel
    chat_service = AzureChatCompletion(
        service_id="azure_gpt4o",
        deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )
    kernel.add_service(chat_service)
    
    sql_generator = SQLGenerator()
    
    test_queries = [
        "show me 3 recent deals",
        "get top 5 trades"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            sql = await sql_generator.generate_sql_from_natural_language(query, kernel)
            print(f"Generated SQL: {sql}")
            
            # Check if it has the correct format
            if "trade_catalog.trade_schema." in sql and "trade_catalog.trade_catalog." not in sql:
                print("✅ Format is CORRECT")
            else:
                print("❌ Format is INCORRECT")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_sql_fix())