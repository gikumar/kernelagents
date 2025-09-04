from abc import ABC, abstractmethod
from semantic_kernel import Kernel

class BaseAgent(ABC):
    def __init__(self, kernel: Kernel, name: str, description: str):
        self.kernel = kernel
        self.name = name
        self.description = description
        self.plugins = []
    
    @abstractmethod
    async def initialize(self):
        """Initialize agent with plugins and services"""
        pass
    
    @abstractmethod
    async def process_request(self, prompt: str, context: dict = None):
        """Process user request"""
        pass
    
    def add_plugin(self, plugin):
        self.plugins.append(plugin)
    
    async def cleanup(self):
        """Cleanup resources"""
        pass