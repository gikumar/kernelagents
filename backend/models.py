# models.py - Pydantic models for agent configuration
from pydantic import BaseModel
from typing import Optional, List, Dict

class AgentConfig(BaseModel):
    name: str
    description: str
    instructions: str
    model: str
    capabilities: Optional[List[str]] = None
    metadata: Optional[Dict] = None

class AgentResponse(BaseModel):
    name: str
    description: str
    agent_id: Optional[str] = None
    status: str

class MultiAgentRequest(BaseModel):
    prompt: str
    agent_name: str
    context: Optional[Dict] = None