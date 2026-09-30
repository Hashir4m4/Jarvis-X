import abc
import logging
from typing import Dict, Any, List
from .agent_models import AgentMetadata, AgentTaskContext, AgentResult, AgentStatus

logger = logging.getLogger("JARVIS.BaseAgent")


class BaseAgent(abc.ABC):
    """
    Common abstraction for all specialized JARVIS internal agents.
    Enforces task capability validation, bounded context handling,
    restricted tool execution, and cancellation guards.
    """

    def __init__(self, metadata: AgentMetadata):
        self.metadata = metadata
        self._cancelled = False

    @property
    def agent_id(self) -> str:
        return self.metadata.agent_id

    @property
    def name(self) -> str:
        return self.metadata.name

    @abc.abstractmethod
    def can_handle(self, task_context: AgentTaskContext) -> bool:
        """Determines if this agent is capable of fulfilling the requested task."""
        pass

    @abc.abstractmethod
    def execute(self, task_context: AgentTaskContext) -> AgentResult:
        """Executes the specialized task within the provided boundaries."""
        pass

    def get_capabilities(self) -> List[str]:
        """Returns the list of capabilities offered by this agent."""
        return [c.value if hasattr(c, "value") else str(c) for c in self.metadata.capabilities]

    def get_status(self) -> AgentStatus:
        """Returns the current operational status of the agent."""
        return self.metadata.status

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Validates if a tool invocation falls within this agent's permission boundaries."""
        target = tool_name.lower().replace("_", ".")
        allowed = [t.lower().replace("_", ".") for t in self.metadata.allowed_tools]
        return target in allowed

    def cancel(self):
        """Signals active agent execution to abort immediately."""
        self._cancelled = True
        self.metadata.status = AgentStatus.CANCELLED
        logger.warning(f"Agent '{self.name}' received cancellation request.")

    def reset_cancellation(self):
        """Resets cancellation flag for future invocations."""
        self._cancelled = False
        self.metadata.status = AgentStatus.IDLE

    def health_check(self) -> Dict[str, Any]:
        """Diagnostics snapshot of the agent."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "status": self.get_status().value,
            "offline_support": self.metadata.offline_support.value,
            "allowed_tools": self.metadata.allowed_tools,
        }
