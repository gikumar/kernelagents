# backend/app/core/service_registry.py
from app.agents.trading_agent import TradingAgent
from app.core.kernel_setup import create_kernel
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AgentRegistry:
    _agents: Dict[str, Any] = {}
    _kernel = None

    @classmethod
    def get_kernel(cls):
        """Get or create the kernel instance"""
        logger.info("⭐ AgentRegistry.get_kernel() - Entry")
        try:
            if cls._kernel is None:
                logger.info("⭐ Decision: Creating new kernel instance")
                cls._kernel = create_kernel()
                logger.info("⭐ Kernel created successfully")
            else:
                logger.info("⭐ Decision: Reusing existing kernel instance")
            
            return cls._kernel
            
        except Exception as e:
            logger.error(f"💥 Error getting kernel: {str(e)}")
            raise
        finally:
            logger.info("⭐ AgentRegistry.get_kernel() - Exit")

    @classmethod
    def register_agent(cls, agent_name: str, agent_class):
        """Register an agent class"""
        logger.info(f"⭐ AgentRegistry.register_agent() - Entry: {agent_name}")
        try:
            if agent_name in cls._agents:
                logger.warning(f"⭐ Agent '{agent_name}' already registered, overwriting")
            
            cls._agents[agent_name] = agent_class
            logger.info(f"⭐ Agent '{agent_name}' registered successfully")
            
        except Exception as e:
            logger.error(f"💥 Error registering agent: {str(e)}")
            raise
        finally:
            logger.info("⭐ AgentRegistry.register_agent() - Exit")

    @classmethod
    def get_agent(cls, agent_name: str):
        """Get or create an agent instance"""
        logger.info(f"⭐ AgentRegistry.get_agent() - Entry: {agent_name}")
        try:
            # Check if agent instance already exists
            if agent_name in cls._agents and isinstance(cls._agents[agent_name], (TradingAgent)):
                logger.info(f"⭐ Decision: Returning existing agent instance for '{agent_name}'")
                return cls._agents[agent_name]
            
            # Create new agent instance
            logger.info(f"⭐ Decision: Creating new agent instance for '{agent_name}'")
            kernel = cls.get_kernel()
            
            if agent_name == "trading":
                agent_instance = TradingAgent(kernel)
            elif agent_name == "docu":
                agent_instance = DocuAgent(kernel)
            else:
                error_msg = f"Unknown agent: {agent_name}"
                logger.error(f"💥 {error_msg}")
                raise ValueError(error_msg)
            
            # Store the instance
            cls._agents[agent_name] = agent_instance
            logger.info(f"⭐ Agent '{agent_name}' created and stored successfully")
            
            return agent_instance
            
        except Exception as e:
            logger.error(f"💥 Error getting agent: {str(e)}")
            raise
        finally:
            logger.info("⭐ AgentRegistry.get_agent() - Exit")

    @classmethod
    async def initialize_all(cls):
        """Initialize all agents"""
        logger.info("⭐ AgentRegistry.initialize_all() - Entry")
        try:
            initialized_count = 0
            for agent_name, agent in cls._agents.items():
                if hasattr(agent, 'initialize') and callable(getattr(agent, 'initialize')):
                    logger.info(f"⭐ Initializing agent: {agent_name}")
                    await agent.initialize()
                    initialized_count += 1
                    logger.info(f"⭐ Agent '{agent_name}' initialized successfully")
                else:
                    logger.warning(f"⭐ Agent '{agent_name}' doesn't have initialize method")
            
            logger.info(f"⭐ Total agents initialized: {initialized_count}")
            
        except Exception as e:
            logger.error(f"💥 Error initializing agents: {str(e)}")
            raise
        finally:
            logger.info("⭐ AgentRegistry.initialize_all() - Exit")

    @classmethod
    def list_agents(cls):
        """List all registered agents"""
        logger.info("⭐ AgentRegistry.list_agents() - Entry")
        try:
            agent_list = list(cls._agents.keys())
            logger.info(f"⭐ Found {len(agent_list)} agents: {agent_list}")
            return agent_list
        except Exception as e:
            logger.error(f"💥 Error listing agents: {str(e)}")
            return []
        finally:
            logger.info("⭐ AgentRegistry.list_agents() - Exit")

    @classmethod
    def get_agent_status(cls, agent_name: str) -> Dict[str, Any]:
        """Get status of a specific agent"""
        logger.info(f"⭐ AgentRegistry.get_agent_status() - Entry: {agent_name}")
        try:
            if agent_name not in cls._agents:
                logger.warning(f"⭐ Agent '{agent_name}' not found")
                return {"status": "not_found", "exists": False}
            
            agent = cls._agents[agent_name]
            status = {
                "status": "initialized" if hasattr(agent, 'initialized') and getattr(agent, 'initialized', False) else "created",
                "exists": True,
                "type": type(agent).__name__
            }
            
            # Add conversation stats for trading agent
            if agent_name == "trading" and hasattr(agent, 'get_conversation_stats'):
                try:
                    status["conversation_stats"] = agent.get_conversation_stats()
                except Exception as e:
                    status["conversation_stats_error"] = str(e)
            
            logger.info(f"⭐ Agent '{agent_name}' status: {status['status']}")
            return status
            
        except Exception as e:
            logger.error(f"💥 Error getting agent status: {str(e)}")
            return {"status": "error", "error": str(e)}
        finally:
            logger.info("⭐ AgentRegistry.get_agent_status() - Exit")

    @classmethod
    async def cleanup_all(cls):
        """Cleanup all agents"""
        logger.info("⭐ AgentRegistry.cleanup_all() - Entry")
        try:
            cleanup_count = 0
            for agent_name, agent in list(cls._agents.items()):
                if hasattr(agent, 'cleanup') and callable(getattr(agent, 'cleanup')):
                    logger.info(f"⭐ Cleaning up agent: {agent_name}")
                    try:
                        await agent.cleanup()
                        cleanup_count += 1
                        logger.info(f"⭐ Agent '{agent_name}' cleaned up successfully")
                    except Exception as e:
                        logger.error(f"💥 Error cleaning up agent '{agent_name}': {str(e)}")
                else:
                    logger.warning(f"⭐ Agent '{agent_name}' doesn't have cleanup method")
            
            # Clear the agents dictionary
            cls._agents.clear()
            logger.info(f"⭐ Total agents cleaned up: {cleanup_count}")
            logger.info("⭐ Agents registry cleared")
            
        except Exception as e:
            logger.error(f"💥 Error during cleanup: {str(e)}")
            raise
        finally:
            logger.info("⭐ AgentRegistry.cleanup_all() - Exit")

    @classmethod
    def get_all_agents_status(cls) -> Dict[str, Any]:
        """Get status of all agents"""
        logger.info("⭐ AgentRegistry.get_all_agents_status() - Entry")
        try:
            status = {}
            for agent_name in cls._agents.keys():
                status[agent_name] = cls.get_agent_status(agent_name)
            
            logger.info(f"⭐ Status retrieved for {len(status)} agents")
            return status
            
        except Exception as e:
            logger.error(f"💥 Error getting all agents status: {str(e)}")
            return {"error": str(e)}
        finally:
            logger.info("⭐ AgentRegistry.get_all_agents_status() - Exit")

# Register available agents
logger.info("⭐ Registering agents in AgentRegistry")
try:
    AgentRegistry.register_agent("trading", TradingAgent)
    logger.info("⭐ Agents registered successfully")
except Exception as e:
    logger.error(f"💥 Error registering agents: {str(e)}")
    raise