
import logging
from typing import Dict, Any, Optional
import os

from backend.kernel.kernel import JarvisKernel
from backend.brain import Brain
from backend.memory_manager import MemoryManager
from backend.automation.security_proxy import SecurityProxy
from backend.agents.agent_manager import AgentManager
from backend.router.tool_registry import ToolRegistry
from backend.skills.registry import SkillRegistry
from backend.router.intent_router import IntentRouter
from backend.agents.agent_registry import AgentRegistry
from backend.agents.specialized import (
    ResearchAgent, CodingAgent, PlanningAgent, AnalysisAgent, SystemAgent, ProductivityAgent
)
from backend.orchestrator.decision_engine import DecisionEngine
from backend.llm.model_router import ModelRouter
from backend.agents.multi_agent_coordinator import MultiAgentCoordinator
from backend.planning import PlanAnalyzer, TaskPlanner, ExecutionEngine
from backend.interaction import InteractionEngine
from backend.orchestrator.orchestrator import JarvisOrchestrator
from backend.proactive import ProactiveEngine, MonitorRegistry
from backend.router.central_router import CentralRouter
from backend.learning.engine import LearningEngine
from backend.goals.engine import GoalManagerEngine
from backend.goals.decomposition import GoalDecompositionEngine


logger = logging.getLogger("JARVIS.Container")

class AppContainer:
    """Deterministic Dependency Injection Container for JARVIS X."""
    def __init__(self, config: Dict[str, Any], session_id: str = "default", skills_dir: Optional[str] = None):
        self.config = config
        self.session_id = session_id
        self.skills_dir = skills_dir

        logger.info("Initializing dependency container...")

        # 1. Base Layer
        self.kernel = JarvisKernel(config)
        self.memory = MemoryManager(config, session_id=session_id)
        self.brain = Brain(config, session_id=session_id)
        self.security = SecurityProxy(config)
        self.decision_engine = DecisionEngine()
        self.model_router = ModelRouter(config)

        # 2. Skill Registry
        if self.skills_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            candidate_skills = os.path.join(base_dir, "skills")
            self.skills_dir = candidate_skills if os.path.isdir(candidate_skills) else None

        self.skill_registry = SkillRegistry(skills_dir=self.skills_dir)

        # 3. Agents Base
        self.agent_manager = AgentManager(
            llm=self.brain.llm,
            security=self.security,
            working_dir="."
        )

        # 4. Tools (Requires agent_manager)
        self.tools = ToolRegistry(agent_manager=self.agent_manager)
        self.tools.register_scheduler_tools(self.kernel.scheduler)

        # 5. Specialized Agents
        self.specialized_registry = AgentRegistry()
        for agent_class in [ResearchAgent, CodingAgent, PlanningAgent, AnalysisAgent, SystemAgent, ProductivityAgent]:
            self.specialized_registry.register(agent_class())

        # 6. Multi-Agent Coordinator
        self.multi_agent_coordinator = MultiAgentCoordinator(
            registry=self.specialized_registry,
            event_bus=self.kernel.event_bus,
            security=self.security,
            tools=self.tools,  # Injected directly
            model_router=self.model_router, # Injected directly
            config=config
        )

        # 7. Planning & Execution
        self.plan_analyzer = PlanAnalyzer(
            skill_registry=self.skill_registry,
            tool_registry=self.tools,
            agent_registry=self.specialized_registry
        )

        self.task_planner = TaskPlanner(
            analyzer=self.plan_analyzer,
            config=config
        )

        self.execution_engine = ExecutionEngine(
            analyzer=self.plan_analyzer,
            skill_registry=self.skill_registry,
            tool_registry=self.tools,
            agent_coordinator=self.multi_agent_coordinator,
            security_proxy=self.security,
            event_bus=self.kernel.event_bus,
            config=config
        )

        # 8. Routers & Interaction
        self.intent_router = IntentRouter(skill_registry=self.skill_registry)

        # 7. Learning System
        self.learning_engine = LearningEngine(self.config, self.kernel.event_bus, self.memory)

        # 8. Goal Management System
        self.goal_engine = GoalManagerEngine(
            memory_api=self.memory,
            event_bus=self.kernel.event_bus,
            security_proxy=self.security,
            config=self.config
        )
        self.goal_decomposition_engine = GoalDecompositionEngine(
            llm_client=getattr(self.brain, "llm", None),
            config=self.config
        )

        self.central_router = CentralRouter(
            skill_registry=self.skill_registry,
            intent_router=self.intent_router,
            memory_api=self.memory,
            tool_registry=self.tools
        )
        self.interaction_engine = InteractionEngine(config=config)

        # 9. Orchestrator
        self.orchestrator = JarvisOrchestrator(
            skill_registry=self.skill_registry,
            intent_router=self.intent_router,
            memory_api=self.memory,
            tool_registry=self.tools,
            agent_manager=self.agent_manager,
            security_proxy=self.security,
            event_bus=self.kernel.event_bus,
            llm_provider=getattr(self.brain.llm, "provider", None) if hasattr(self.brain, "llm") else None,
            config=config,
            multi_agent_coordinator=self.multi_agent_coordinator,
            task_planner=self.task_planner,
            execution_engine=self.execution_engine,
            interaction_engine=self.interaction_engine
        )
        self.orchestrator.decision_engine = self.decision_engine
        self.orchestrator.model_router = self.model_router

        # 10. Proactive Engine
        self.monitor_registry = MonitorRegistry(
            event_bus=self.kernel.event_bus,
            system_controller=self.tools.system_ctrl if hasattr(self.tools, "system_ctrl") else None
        )

        self.proactive_engine = ProactiveEngine(
            event_bus=self.kernel.event_bus,
            monitor_registry=self.monitor_registry,
            config=config,
            # Prompt 54 injections
            memory_system=self.memory,
            task_planner=self.task_planner,
            execution_engine=self.execution_engine,
            security_proxy=self.security,
            orchestrator=self.orchestrator,
            decision_engine=self.decision_engine
        )
