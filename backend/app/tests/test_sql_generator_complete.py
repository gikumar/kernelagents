# backend/test_sql_generator_complete.py
import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from sql_generator import SQLGenerator
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

async def test_sql_generator_complete():
    """Complete test of SQL generator functionality"""
    print("🧪 Testing SQL Generator Complete...")
    
    # Test 1: Schema loading
    print("\n1. Testing Schema Loading...")
    try:
        sql_generator = SQLGenerator()
        
        tables = sql_generator.get_available_tables()
        print(f"   📋 Loaded {len(tables)} tables: {tables}")
        
        if tables:
            sample_table = tables[0]
            columns = sql_generator.get_table_columns(sample_table)
            print(f"   📊 Table '{sample_table}' has {len(columns)} columns")
            print(f"   🔍 Sample columns: {columns[:5]}...")
    except Exception as e:
        print(f"   ❌ Schema loading failed: {str(e)}")
        return
    
    # Test 2: Limit extraction
    print("\n2. Testing Limit Extraction...")
    test_queries = [
        "show me 5 recent trades",
        "get top 10 deals",
        "first 3 records",
        "find trades with amount > 1000",
        "summary of data"
    ]
    
    for query in test_queries:
        try:
            limit = sql_generator._extract_limit_from_query(query)
            print(f"   📝 '{query}' -> limit: {limit}")
        except Exception as e:
            print(f"   ❌ Limit extraction error for '{query}': {str(e)}")
    
    # Test 3: SQL safety validation
    print("\n3. Testing SQL Safety Validation...")
    test_sql_queries = [
        "SELECT * FROM trades",  # Safe
        "DROP TABLE trades",     # Unsafe
        "SELECT * FROM table1; DROP TABLE table2",  # Unsafe
        "WITH data AS (SELECT * FROM trades) SELECT * FROM data"  # Safe
    ]
    
    for sql in test_sql_queries:
        try:
            is_safe = sql_generator._validate_sql_safety(sql)
            print(f"   🔒 '{sql[:30]}...' -> Safe: {is_safe}")
        except Exception as e:
            print(f"   ❌ Safety validation error for SQL: {str(e)}")
    
    # Test 4: Environment variables check
    print("\n4. Testing Environment Variables...")
    
    # Manually load environment variables
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    
    print(f"   🔍 Looking for .env file at: {env_path}")
    print(f"   📁 .env file exists: {env_path.exists()}")
    
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print("   ✅ .env file loaded")
    else:
        print("   ⚠️ .env file not found, checking system environment variables")
    
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    
    # Print configuration status (without exposing sensitive data)
    print(f"   🔧 AZURE_OPENAI_ENDPOINT: {'✅ Set' if endpoint else '❌ Missing'}")
    print(f"   🔧 AZURE_OPENAI_API_KEY: {'✅ Set' if api_key else '❌ Missing'}")
    print(f"   🔧 AZURE_OPENAI_DEPLOYMENT: {'✅ Set (' + deployment + ')' if deployment else '❌ Missing'}")
    print(f"   🔧 AZURE_OPENAI_API_VERSION: {api_version}")
    
    if endpoint:
        print(f"   🌐 Endpoint URL format check: {endpoint.startswith('https://')}")
    
    if not all([endpoint, api_key, deployment]):
        print("   ⚠️ Azure OpenAI not configured properly, skipping LLM test")
        return
    
    # Test 5: Azure OpenAI connection
    print("\n5. Testing Azure OpenAI Connection...")
    
    try:
        kernel = Kernel()
        
        chat_service = AzureChatCompletion(
            service_id="azure_gpt4o",
            deployment_name=deployment,
            endpoint=endpoint,
            api_key=api_key,
            api_version=api_version
        )
        
        kernel.add_service(chat_service)
        print("   ✅ Azure OpenAI service initialized")
        
        # Test 6: Simple SQL generation
        print("\n6. Testing SQL Generation with LLM...")
        simple_queries = [
            "show me 2 recent trades",
            "get 1 deal",
            "select top 1 record from trades"
        ]
        
        for i, query in enumerate(simple_queries, 1):
            print(f"   📝 Test {i}: {query}")
            try:
                sql = await sql_generator.generate_sql_from_natural_language(query, kernel)
                print(f"   📋 Generated SQL: {sql}")
                print(f"   🔒 Safety check: {sql_generator._validate_sql_safety(sql)}")
                print(f"   ✅ Test {i} completed successfully")
            except Exception as e:
                print(f"   ❌ Test {i} failed: {str(e)}")
                print(f"   🔍 Error type: {type(e).__name__}")
                # Continue with other tests instead of breaking
        
    except Exception as e:
        print(f"   ❌ Azure OpenAI initialization failed: {str(e)}")
        print(f"   🔍 Error type: {type(e).__name__}")
        
        # Additional debugging information
        if "authentication" in str(e).lower() or "401" in str(e):
            print("   💡 This looks like an authentication issue. Check your API key.")
        elif "endpoint" in str(e).lower() or "404" in str(e):
            print("   💡 This looks like an endpoint issue. Check your endpoint URL.")
        elif "deployment" in str(e).lower():
            print("   💡 This looks like a deployment issue. Check your deployment name.")
        elif "version" in str(e).lower():
            print("   💡 This might be an API version issue. Try a different version.")

if __name__ == "__main__":
    try:
        asyncio.run(test_sql_generator_complete())
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()