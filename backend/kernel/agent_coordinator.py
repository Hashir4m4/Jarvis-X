import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class AgentCoordinator:
    """
    Registry and coordinator for all autonomous agents in Jarvis OS.
    Agents register here so they can be discovered and managed by the Kernel.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._agents: Dict[str, Any] = {}

    def register_agent(self, name: str, agent_instance: Any):
        """Registers a new agent."""
        if name in self._agents:
            logger.warning(f"Agent '{name}' is already registered. Overwriting.")
        
        self._agents[name] = agent_instance
        logger.info(f"Agent '{name}' registered successfully.")

    def get_agent(self, name: str) -> Any:
        """Retrieves an agent by name."""
        return self._agents.get(name)

    async def broadcast_state(self):
        """Broadcasts the status of all agents to the event bus."""
        states = {}
        for name, agent in self._agents.items():
            # Agents should ideally implement a get_state() method
            if hasattr(agent, "get_state"):
                states[name] = agent.get_state()
            else:
                states[name] = "online"
                
        await self.event_bus.publish("agent_status_update", states)
