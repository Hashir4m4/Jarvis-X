import logging
from typing import Dict, List, Optional, Any
from .base_agent import BaseAgent
from .agent_models import AgentTaskContext, AgentStatus

logger = logging.getLogger("JARVIS.AgentRegistry")


class AgentRegistry:
    """
    Central discovery, lifecycle, and security registry for JARVIS specialized agents.
    Enforces uniqueness of agent IDs, tool permission boundaries, and capability resolution.
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        """
        Registers an agent into the registry.
        Rejects duplicate agent IDs to ensure deterministic routing.
        """
        aid = agent.agent_id.lower().strip()
        if aid in self._agents:
            logger.error(f"Duplicate agent ID detected: '{aid}'")
            raise ValueError(f"Agent with ID '{aid}' is already registered.")

        self._agents[aid] = agent
        logger.info(f"Registered Agent: '{agent.name}' (ID: {aid}, Specialization: {agent.metadata.specialization})")

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Retrieves an agent by its unique identifier."""
        return self._agents.get(agent_id.lower().strip())

    def has_agent(self, agent_id: str) -> bool:
        """Checks if an agent exists in the registry."""
        return agent_id.lower().strip() in self._agents

    def get_metadata(self, agent_id: str) -> Optional[Any]:
        """Returns the AgentMetadata for a given agent ID."""
        agent = self.get_agent(agent_id)
        return agent.metadata if agent else None

    def find_by_capability(self, capability: Any) -> List[BaseAgent]:
        """Finds all agents possessing a specific capability."""
        cap_val = capability.value if hasattr(capability, "value") else str(capability)
        matches = []
        for agent in self._agents.values():
            caps = [c.value if hasattr(c, "value") else str(c) for c in agent.metadata.capabilities]
            if cap_val in caps:
                matches.append(agent)
        return matches

    def find_agents_for_task(self, task_context: AgentTaskContext) -> List[BaseAgent]:
        """Discovers which registered agents are capable of handling the task."""
        candidates = []
        for agent in self._agents.values():
            if agent.get_status() != AgentStatus.UNAVAILABLE and agent.can_handle(task_context):
                candidates.append(agent)
        return candidates

    def list_agents(self) -> List[Dict[str, Any]]:
        """Returns structured metadata for all registered agents."""
        return [a.metadata.to_dict() for a in self._agents.values()]

    def cancel_all(self):
        """Broadcasts cancellation signal to all registered agents."""
        for agent in self._agents.values():
            agent.cancel()

    def health_check_all(self) -> Dict[str, Any]:
        """Diagnostics summary for all agents."""
        return {
            "total_agents": len(self._agents),
            "agents": {aid: a.health_check() for aid, a in self._agents.items()}
        }
