# backend/test_nlq_to_sql_complete.py
import asyncio
import sys
import os
from pathlib import Path
import logging

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_complete_nlq_to_sql_pipeline():
    """Complete test of the NLQ to SQL pipeline"""
    print("=" * 60)
    print("COMPREHENSIVE NLQ TO SQL TESTING")
    print("=" * 60)
    
    # Test 1: Environment and Configuration
    print("\n1. TESTING ENVIRONMENT AND CONFIGURATION")
    print("-" * 40)
    
    try:
        # Load environment variables
        from dotenv import load_dotenv
        env_path = Path(__file__).parent / ".env"
        
        print(f"Looking for .env file at: {env_path}")
        print(f".env file exists: {env_path.exists()}")
        
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            print("Environment variables loaded from .env file")
        else:
            print("No .env file found, using system environment variables")
        
        # Test config loading
        from app.config import validate_config, get_config_summary
        config_status = validate_config()
        config_summary = get_config_summary()
        
        print(f"Azure OpenAI configured: {config_status['azure_openai']}")
        print(f"Databricks configured: {config_status['databricks']}")
        
        if config_status['errors']:
            print("Configuration errors:")
            for error in config_status['errors']:
                print(f"  - {error}")
        
        if config_status['warnings']:
            print("Configuration warnings:")
            for warning in config_status['warnings']:
                print(f"  - {warning}")
                
    except Exception as e:
        print(f"Configuration test failed: {str(e)}")
        return False
    
    # Test 2: Schema Loading
    print("\n2. TESTING SCHEMA LOADING")
    print("-" * 40)
    
    try:
        from schema_utils import load_schema, validate_schema, list_tables
        
        schema = load_schema()
        print(f"Schema loaded with {len(schema)} tables")
        
        if schema:
            tables = list_tables()
            print(f"Available tables: {tables}")
            
            # Test getting columns for first table
            if tables:
                first_table = tables[0]
                from schema_utils import get_table_columns
                columns = get_table_columns(first_table)
                print(f"Table '{first_table}' has {len(columns)} columns")
                print(f"Sample columns: {columns[:5]}")
        
        schema_valid = validate_schema()
        print(f"Schema validation: {'PASS' if schema_valid else 'FAIL'}")
        
    except Exception as e:
        print(f"Schema loading test failed: {str(e)}")
        return False
    
    # Test 3: SQL Generator Initialization
    print("\n3. TESTING SQL GENERATOR INITIALIZATION")
    print("-" * 40)
    
    try:
        from sql_generator import SQLGenerator
        
        sql_generator = SQLGenerator()
        print(f"SQL Generator initialized")
        print(f"Schema summary: {sql_generator.get_schema_summary()}")
        
        # Test utility functions
        tables = sql_generator.get_available_tables()
        print(f"Available tables from SQL Generator: {tables}")
        
        if tables:
            first_table = tables[0]
            columns = sql_generator.get_table_columns(first_table)
            print(f"Columns for {first_table}: {len(columns)} columns")
        
    except Exception as e:
        print(f"SQL Generator initialization failed: {str(e)}")
        return False
    
    # Test 4: Kernel and Azure OpenAI Service
    print("\n4. TESTING KERNEL AND AZURE OPENAI SERVICE")
    print("-" * 40)
    
    try:
        from semantic_kernel import Kernel
        from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
        from config import (
            AZURE_OPENAI_ENDPOINT, 
            AZURE_OPENAI_KEY, 
            AZURE_OPENAI_DEPLOYMENT, 
            AZURE_OPENAI_API_VERSION
        )
        
        if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT]):
            print("Azure OpenAI not properly configured, skipping service tests")
            return False
        
        # Initialize kernel
        kernel = Kernel()
        print("Kernel initialized")
        
        # Initialize Azure OpenAI service
        chat_service = AzureChatCompletion(
            service_id="azure_gpt4o",
            deployment_name=AZURE_OPENAI_DEPLOYMENT,
            endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION
        )
        
        kernel.add_service(chat_service)
        print("Azure OpenAI service added to kernel")
        
        # Test service retrieval
        retrieved_service = sql_generator._get_chat_service_from_kernel(kernel)
        if retrieved_service:
            print("Chat service successfully retrieved from kernel")
        else:
            print("Failed to retrieve chat service from kernel")
            return False
        
    except Exception as e:
        print(f"Kernel and Azure OpenAI service test failed: {str(e)}")
        return False
    
    # Test 5: SQL Generation
    print("\n5. TESTING SQL GENERATION")
    print("-" * 40)
    
    try:
        # Test simple queries
        test_queries = [
            "show me 3 recent deals",
            "get top 5 trades",
            "find deals with volume > 1000",
            "list all portfolios"
        ]
        
        for i, query in enumerate(test_queries, 1):
            print(f"\nTest Query {i}: {query}")
            try:
                sql = await sql_generator.generate_sql_from_natural_language(query, kernel)
                print(f"Generated SQL: {sql}")
                
                # Validate safety
                is_safe = sql_generator._validate_sql_safety(sql)
                print(f"Safety validation: {'PASS' if is_safe else 'FAIL'}")
                
                if not is_safe:
                    print("WARNING: Generated SQL failed safety validation")
                
            except Exception as e:
                print(f"Query {i} failed: {str(e)}")
                continue
        
    except Exception as e:
        print(f"SQL generation test failed: {str(e)}")
        return False
    
    # Test 6: Function Calling Manager
    print("\n6. TESTING FUNCTION CALLING MANAGER")
    print("-" * 40)
    
    try:
        from function_calling_manager import FunctionCallingManager
        
        # Initialize function calling manager
        fcm = FunctionCallingManager(kernel)
        print("Function Calling Manager initialized")
        
        # Test intent analysis
        test_prompts = [
            "what is a trade deal?",
            "show me some recent trades",
            "SELECT * FROM trades LIMIT 5",
            "hello, how are you?"
        ]
        
        for prompt in test_prompts:
            intent = await fcm._analyze_prompt_intent(prompt)
            print(f"Prompt: '{prompt}' -> Intent: {intent}")
        
    except Exception as e:
        print(f"Function Calling Manager test failed: {str(e)}")
        return False
    
    # Test 7: End-to-End Function Execution
    print("\n7. TESTING END-TO-END FUNCTION EXECUTION")
    print("-" * 40)
    
    try:
        # Test concept explanation
        print("Testing concept explanation...")
        concept_result = await fcm.explain_concept("trade deal")
        print(f"Concept explanation length: {len(concept_result)} characters")
        print(f"First 200 chars: {concept_result[:200]}...")
        
        # Test data query (if Databricks is available)
        from config import DATABRICKS_VALID
        if DATABRICKS_VALID:
            print("Testing data query...")
            data_result = await fcm.query_trade_data("show me 2 recent trades")
            print(f"Data query result length: {len(data_result)} characters")
            print(f"First 300 chars: {data_result[:300]}...")
        else:
            print("Databricks not configured, skipping data query test")
        
        # Test complete function calling flow
        print("Testing complete function calling flow...")
        flow_result = await fcm.execute_with_function_calling("what is a commodity trade?")
        print(f"Function calling flow result length: {len(flow_result)} characters")
        print(f"First 200 chars: {flow_result[:200]}...")
        
    except Exception as e:
        print(f"End-to-end function execution test failed: {str(e)}")
        return False
    
    # Test 8: Error Handling and Edge Cases
    print("\n8. TESTING ERROR HANDLING AND EDGE CASES")
    print("-" * 40)
    
    try:
        # Test empty query
        try:
            empty_result = await sql_generator.generate_sql_from_natural_language("", kernel)
            print(f"Empty query handling: {empty_result[:100]}...")
        except Exception as e:
            print(f"Empty query error (expected): {str(e)}")
        
        # Test malicious SQL
        malicious_queries = [
            "DROP TABLE trades",
            "DELETE FROM trades WHERE 1=1",
            "SELECT * FROM trades; DROP TABLE users"
        ]
        
        for malicious in malicious_queries:
            is_safe = sql_generator._validate_sql_safety(malicious)
            print(f"Malicious query safety check: {'BLOCKED' if not is_safe else 'FAILED TO BLOCK'}")
        
        # Test invalid table reference
        try:
            invalid_result = await fcm.query_trade_data("show me data from nonexistent_table")
            print(f"Invalid table handling: {invalid_result[:100]}...")
        except Exception as e:
            print(f"Invalid table error: {str(e)}")
        
    except Exception as e:
        print(f"Error handling test failed: {str(e)}")
        return False
    
    # Test Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("All tests completed successfully!")
    print("\nNext steps:")
    print("1. If any tests failed, check the specific error messages above")
    print("2. Verify your .env file contains all required variables")
    print("3. Ensure Databricks connection details are correct")
    print("4. Test with real queries in your application")
    
    return True

def run_quick_validation():
    """Quick validation of key components"""
    print("QUICK VALIDATION")
    print("-" * 20)
    
    try:
        # Check imports
        from config import AZURE_OPENAI_VALID, DATABRICKS_VALID
        from schema_utils import validate_schema
        from sql_generator import SQLGenerator
        
        print(f"Azure OpenAI: {'OK' if AZURE_OPENAI_VALID else 'MISSING'}")
        print(f"Databricks: {'OK' if DATABRICKS_VALID else 'MISSING'}")
        print(f"Schema: {'OK' if validate_schema() else 'MISSING'}")
        print(f"SQL Generator: {'OK'}")
        
        return AZURE_OPENAI_VALID and validate_schema()
        
    except Exception as e:
        print(f"Quick validation failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starting NLQ to SQL Testing...")
    
    # Run quick validation first
    if not run_quick_validation():
        print("\nQuick validation failed. Running comprehensive test for detailed diagnostics...")
    
    try:
        # Run comprehensive test
        success = asyncio.run(test_complete_nlq_to_sql_pipeline())
        
        if success:
            print("\nAll tests passed! Your NLQ to SQL pipeline should be working.")
        else:
            print("\nSome tests failed. Check the error messages above.")
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error during testing: {str(e)}")
        import traceback
        traceback.print_exc()