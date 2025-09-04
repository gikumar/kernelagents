from abc import ABC, abstractmethod
from semantic_kernel import Kernel

"""ABC stands for Abstract Base Class from Python's abc module. It's a way to create "blueprint" classes that:
Your BasePlugin is an abstract base class that defines the contract for all plugins in your system:"""
class BasePlugin(ABC):
    def __init__(self, kernel: Kernel, plugin_name: str):
        self.kernel = kernel
        self.plugin_name = plugin_name
    
    @abstractmethod
    async def initialize(self):
        """Initialize plugin resources"""
        pass