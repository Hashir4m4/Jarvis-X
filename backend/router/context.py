from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.core.models import InputChannel, Intent, TaskCategory, ExecutionState, JarvisError


@dataclass
class ExecutionContext:
    """
    Unified ExecutionContext assembled and maintained across the intelligence pipeline.
    Tracks context analysis, memory retrieval, task classification, execution strategy,
    selected capabilities, permission validation, result verification, and observability.
    """
    # 1. Identity & Ingestion Source
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: InputChannel = InputChannel.TEXT
    channel: Optional[InputChannel] = None
    user_input: str = ""
    resolved_input: Optional[str] = None
    session_id: str = "default"
    active_task_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    # 2. Context & Memory State
    conversation_context: List[Dict[str, str]] = field(default_factory=list)
    context_messages: Optional[List[Dict[str, str]]] = None
    relevant_memory: List[Dict[str, Any]] = field(default_factory=list)
    recent_telemetry: Dict[str, Any] = field(default_factory=dict)
    user_profile: Dict[str, Any] = field(default_factory=dict)

    # 3. Intent & Task Understanding
    detected_intent: Optional[Intent] = None
    task_category: TaskCategory = TaskCategory.UNKNOWN
    requires_memory_search: bool = False
    is_multi_step: bool = False

    # 4. Capability & Strategy Selection
    selected_skill: Optional[str] = None
    selected_model: Optional[str] = None  # "local:qwen2.5-coder:7b" | "cloud:gpt-4o-mini" | "none"
    selected_tools: List[str] = field(default_factory=list)
    selected_agents: List[str] = field(default_factory=list)
    execution_strategy: str = "direct_skill"  # "direct_skill" | "multi_agent" | "research_pipeline" | "conversation"

    # 4b. Model Router Telemetry
    routing_status: str = "AVAILABLE"    # AVAILABLE | PROCESSING | FALLBACK | NO_CAPABILITY
    routing_reason: str = ""             # Concise routing explanation for logs/debugging
    privacy_policy: str = "PREFER_LOCAL" # LOCAL_ONLY | PREFER_LOCAL | CLOUD_ALLOWED

    # 5. Security & Permissions
    permission_level: str = "READ"  # "READ" | "WRITE" | "EXECUTE" | "DESTRUCTIVE"
    confirmation_required: bool = False
    confirmation_granted: bool = False
    permissions: List[str] = field(default_factory=lambda: ["*"])

    # 6. Execution Lifecycle & Verification
    execution_status: ExecutionState = ExecutionState.IDLE
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Any] = None
    errors: List[JarvisError] = field(default_factory=list)
    needs_verification: bool = False
    verification_passed: bool = True
    should_save_memory: bool = False

    # 7. Deliverables & Telemetry
    actions: List[str] = field(default_factory=list)
    memory_updates: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    timeout_seconds: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 8. Personality & Interaction System
    # Carries the ResponseStrategy determined by InteractionEngine.pre_process().
    # Type is Any to avoid hard coupling the router to the interaction package.
    interaction_strategy: Optional[Any] = None
    interaction_channel_output: Optional[Any] = None

    def __post_init__(self):
        if self.channel is not None:
            self.source = self.channel
        else:
            self.channel = self.source
        if self.context_messages is not None:
            self.conversation_context = self.context_messages
        else:
            self.context_messages = self.conversation_context

    def log_step(self, stage: str, details: Optional[Dict[str, Any]] = None):
        """Records a step in the execution history."""
        self.execution_history.append({
            "stage": stage,
            "timestamp": time.time(),
            "details": details or {}
        })

    def to_dict(self) -> Dict[str, Any]:
        """Converts execution context into serializable dictionary."""
        return {
            "request_id": self.request_id,
            "source": self.source.value if hasattr(self.source, "value") else str(self.source),
            "user_input": self.user_input,
            "timestamp": self.timestamp,
            "task_category": self.task_category.value if hasattr(self.task_category, "value") else str(self.task_category),
            "intent": self.detected_intent.__dict__ if self.detected_intent else None,
            "selected_skill": self.selected_skill,
            "selected_model": self.selected_model,
            "selected_tools": self.selected_tools,
            "selected_agents": self.selected_agents,
            "permission_level": self.permission_level,
            "execution_status": self.execution_status.value if hasattr(self.execution_status, "value") else str(self.execution_status),
            "execution_time_ms": self.execution_time_ms,
            "errors": [e.to_dict() for e in self.errors],
            "actions": self.actions,
            "memory_updates": self.memory_updates,
            "data": self.data
        }


@dataclass
class RouterExecutionResult:
    """
    Standardized execution payload returned by the Central JARVIS Router and Orchestrator.
    """
    intent: Dict[str, Any]
    skill: str
    status: str  # "success", "error", "ambiguous", "timeout", "permission_denied"
    response: str
    actions: List[str] = field(default_factory=list)
    memory_updates: List[Dict[str, Any]] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    request_id: str = ""
    state: ExecutionState = ExecutionState.COMPLETED
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "skill": self.skill,
            "status": self.status,
            "response": self.response,
            "actions": self.actions,
            "memory_updates": self.memory_updates,
            "data": self.data,
            "execution_time_ms": self.execution_time_ms,
            "request_id": self.request_id,
            "state": self.state.value if hasattr(self.state, "value") else str(self.state),
            "errors": self.errors
        }
