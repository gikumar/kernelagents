# backend/test_sql_generation.py
import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from sql_generator import SQLGenerator
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

async def test_sql_generation():
    """Test the SQL generation functionality"""
    print("🧪 Testing SQL Generation...")
    
    # Initialize components with proper Azure OpenAI setup
    kernel = Kernel()
    
    try:
        from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
        
        # Add Azure OpenAI service to kernel
        chat_service = AzureChatCompletion(
            service_id="azure_gpt4o",
            deployment_name=AZURE_OPENAI_DEPLOYMENT,
            endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        
        kernel.add_service(chat_service)
        print("✅ Azure OpenAI service initialized successfully")
        
    except ImportError as e:
        print(f"❌ Config import error: {e}")
        return
    except Exception as e:
        print(f"❌ Azure OpenAI initialization error: {e}")
        return
    
    sql_generator = SQLGenerator()
    
    # Test queries
    test_queries = [
        "show me 5 recent trades",
        "get the top 3 most profitable deals",
        "find trades with amount greater than 10000",
        "summary of P&L by portfolio",
        "count of completed trades by status"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: {query}")
        try:
            sql = await sql_generator.generate_sql_from_natural_language(query, kernel)
            print(f"📋 Generated SQL: {sql}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_sql_generation())