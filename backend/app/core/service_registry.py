from app.agents.trading_agent import TradingAgent

class AgentRegistry:
    _agents = {}
    
    @classmethod
    def register_agent(cls, agent_name: str, agent_class):
        cls._agents[agent_name] = agent_class
    
    @classmethod
    def get_agent(cls, agent_name: str, kernel):
        if agent_name not in cls._agents:
            raise ValueError(f"Agent {agent_name} not registered")
        return cls._agents[agent_name](kernel)
    
    @classmethod
    def list_agents(cls):
        return list(cls._agents.keys())

# Register available agents
AgentRegistry.register_agent("trading", TradingAgent)