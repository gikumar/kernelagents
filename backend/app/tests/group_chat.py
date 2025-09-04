# group_chat.py - Robust Group Chat implementation
import os
from typing import List, Dict, Optional

try:
    # Primary import location (newer versions)
    from azure.ai.agents import AzureAIAgent
    from azure.ai.agents.group_chat import GroupChat, GroupChatOrchestrator, Agent
    HAS_GROUP_CHAT = True
    print("Using azure.ai.agents group chat features")
except ImportError:
    try:
        # Fallback import location (older versions)
        from semantic_kernel.agents import AzureAIAgent
        from semantic_kernel.agents.group_chat import GroupChat, GroupChatOrchestrator, Agent
        HAS_GROUP_CHAT = True
        print("Using semantic_kernel.agents group chat features")
    except ImportError:
        # Final fallback
        HAS_GROUP_CHAT = False
        print("Group chat features not available")

class GroupChatManager:
    def __init__(self, kernel, azure_ai_client):
        self.kernel = kernel
        self.client = azure_ai_client
        self.group_chats: Dict[str, GroupChat] = {}
        self.orchestrators: Dict[str, GroupChatOrchestrator] = {}
    
    async def create_agent_from_config(self, agent_config: Dict):
        """Create an agent from configuration"""
        if not HAS_GROUP_CHAT:
            raise ImportError("Group chat features not available")
        
        # Check if agent already exists in Azure AI
        existing_agent = await self._find_agent_by_name(agent_config["name"])
        
        if existing_agent:
            print(f"Using existing agent: {agent_config['name']}")
            azure_agent = AzureAIAgent(
                definition=existing_agent,
                kernel=self.kernel,
                client=self.client
            )
        else:
            print(f"Creating new agent: {agent_config['name']}")
            created_agent = await self.client.agents.create_agent(body=agent_config)
            azure_agent = AzureAIAgent(
                definition=created_agent,
                kernel=self.kernel,
                client=self.client
            )
        
        # Convert to Group Chat Agent
        return Agent(
            name=agent_config["name"],
            description=agent_config["description"],
            agent=azure_agent
        )
    
    async def _find_agent_by_name(self, agent_name: str):
        """Find an existing agent by name"""
        try:
            async for agent in self.client.agents.list_agents():
                if agent.name.lower() == agent_name.lower():
                    return agent
            return None
        except Exception as e:
            print(f"Error searching for agent: {str(e)}")
            return None
    
    async def create_group_chat(self, chat_id: str, agent_configs: List[Dict], 
                               orchestrator_config: Optional[Dict] = None):
        """Create a new group chat with multiple agents"""
        if not HAS_GROUP_CHAT:
            raise ImportError("Group chat features not available")
        
        # Create agents
        agents = []
        for config in agent_configs:
            agent = await self.create_agent_from_config(config)
            agents.append(agent)
        
        # Create group chat
        group_chat = GroupChat(agents=agents)
        
        # Create orchestrator
        orchestrator_config = orchestrator_config or {
            "name": "GroupOrchestrator",
            "description": "Group chat orchestrator",
            "instructions": "You are a skilled moderator that facilitates conversations between multiple agents.",
            "model": os.getenv("AZURE_OPENAI_DEPLOYMENT")
        }
        
        orchestrator_agent = await self.create_agent_from_config(orchestrator_config)
        orchestrator = GroupChatOrchestrator(agent=orchestrator_agent)
        
        # Store references
        self.group_chats[chat_id] = group_chat
        self.orchestrators[chat_id] = orchestrator
        
        return group_chat, orchestrator
    
    async def send_message(self, chat_id: str, message: str, max_turns: int = 5):
        """Send a message to the group chat"""
        if not HAS_GROUP_CHAT:
            raise ImportError("Group chat features not available")
        
        if chat_id not in self.group_chats:
            raise ValueError(f"Group chat {chat_id} not found")
        
        group_chat = self.group_chats[chat_id]
        orchestrator = self.orchestrators[chat_id]
        
        # Add user message
        group_chat.add_message(role="user", content=message)
        
        # Get response through orchestrator
        responses = []
        async for response in orchestrator.invoke(group_chat, max_turns=max_turns):
            responses.append(response.content)
        
        return " ".join(responses)
    
    def get_chat_history(self, chat_id: str):
        """Get chat history for a group chat"""
        if not HAS_GROUP_CHAT or chat_id not in self.group_chats:
            return []
        
        return [{"role": msg.role, "content": msg.content} for msg in self.group_chats[chat_id].messages]
    
    def list_group_chats(self):
        """List all active group chats"""
        return list(self.group_chats.keys())

# Pre-defined agent configurations
GROUP_CHAT_AGENTS = {
    "brainstorming": [
        {
            "name": "CreativeIdeaGenerator",
            "description": "Generates creative ideas and concepts",
            "instructions": "You are a creative thinker who generates innovative ideas.",
            "model": os.getenv("AZURE_OPENAI_DEPLOYMENT")
        },
        {
            "name": "TechnicalEvaluator",
            "description": "Evaluates ideas from technical perspective",
            "instructions": "You are a technical expert who evaluates ideas for feasibility.",
            "model": os.getenv("AZURE_OPENAI_DEPLOYMENT")
        }
    ]
}