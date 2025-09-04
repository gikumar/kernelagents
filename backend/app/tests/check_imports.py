"""
Diagnostic script to check what group chat features are available
"""
try:
    # Check new location (from migration guide)
    from azure.ai.agents import AzureAIAgent
    print("✅ azure.ai.agents.AzureAIAgent - AVAILABLE")
except ImportError as e:
    print(f"❌ azure.ai.agents.AzureAIAgent - NOT AVAILABLE: {e}")

try:
    from azure.ai.agents.group_chat import GroupChat, GroupChatOrchestrator, Agent
    print("✅ azure.ai.agents.group_chat - AVAILABLE")
except ImportError as e:
    print(f"❌ azure.ai.agents.group_chat - NOT AVAILABLE: {e}")

try:
    # Check old location (for backward compatibility)
    from semantic_kernel.agents import AzureAIAgent as SKAzureAIAgent
    print("✅ semantic_kernel.agents.AzureAIAgent - AVAILABLE")
except ImportError as e:
    print(f"❌ semantic_kernel.agents.AzureAIAgent - NOT AVAILABLE: {e}")

try:
    from semantic_kernel.agents.group_chat import GroupChat as SKGroupChat, GroupChatOrchestrator as SKOrchestrator, Agent as SKAgent
    print("✅ semantic_kernel.agents.group_chat - AVAILABLE")
except ImportError as e:
    print(f"❌ semantic_kernel.agents.group_chat - NOT AVAILABLE: {e}")

# Check versions
try:
    import semantic_kernel as sk
    print(f"✅ semantic_kernel version: {sk.__version__}")
except ImportError as e:
    print(f"❌ semantic_kernel: {e}")

try:
    import azure.ai.agents as aaa
    print(f"✅ azure.ai.agents version: {getattr(aaa, '__version__', 'unknown')}")
except ImportError as e:
    print(f"❌ azure.ai.agents: {e}")