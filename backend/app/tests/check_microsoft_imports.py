"""
Microsoft-specific import diagnostic
"""
print("=== Microsoft Group Chat Migration Import Check ===")

# Check all possible Microsoft-specified imports
imports_to_check = [
    "azure.ai.agents",
    "azure.ai.agents.group_chat",
    "azure.ai.agents.group_chat.GroupChat",
    "azure.ai.agents.group_chat.GroupChatOrchestrator", 
    "azure.ai.agents.group_chat.Agent",
    "azure.ai.agents.group_chat.RoundRobinGroupChatManager",
    "semantic_kernel.agents",
    "semantic_kernel.agents.group_chat",
    "semantic_kernel.agents.group_chat.GroupChat",
    "semantic_kernel.agents.group_chat.GroupChatOrchestrator",
    "semantic_kernel.agents.group_chat.Agent",
    "semantic_kernel.agents.group_chat.RoundRobinGroupChatManager"
]

for import_path in imports_to_check:
    try:
        # Split the import path
        if '.' in import_path:
            module_path, attr_name = import_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[attr_name])
            imported = getattr(module, attr_name)
            print(f"✅ {import_path} - AVAILABLE")
        else:
            __import__(import_path)
            print(f"✅ {import_path} - AVAILABLE")
    except ImportError as e:
        print(f"❌ {import_path} - NOT AVAILABLE: {e}")
    except AttributeError as e:
        print(f"❌ {import_path} - NOT AVAILABLE: {e}")
    except Exception as e:
        print(f"❌ {import_path} - ERROR: {e}")

print("\n=== Package Versions ===")
try:
    import semantic_kernel as sk
    print(f"semantic_kernel: {sk.__version__}")
except:
    print("semantic_kernel: Not available")

try:
    import azure.ai.agents as aaa
    print(f"azure.ai.agents: {getattr(aaa, '__version__', 'unknown')}")
except:
    print("azure.ai.agents: Not available")

try:
    import azure.ai.projects as aap
    print(f"azure.ai.projects: {getattr(aap, '__version__', 'unknown')}")
except:
    print("azure.ai.projects: Not available")