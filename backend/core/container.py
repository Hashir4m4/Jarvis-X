
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
from backend.planning.long_horizon_engine import LongHorizonPlanningEngine
from backend.planning.adaptive_planning import AdaptivePlanningSubsystem


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

        # 8.1 Long-Horizon & Adaptive Planning
        self.planning_engine = LongHorizonPlanningEngine(
            goal_engine=self.goal_engine,
            memory_api=self.memory,
            event_bus=self.kernel.event_bus,
            security_proxy=self.security,
            llm_client=getattr(self.brain, "llm", None),
            config=self.config
        )
        self.adaptive_planning = AdaptivePlanningSubsystem(
            planning_engine=self.planning_engine,
            goal_engine=self.goal_engine,
            event_bus=self.kernel.event_bus,
            security_proxy=self.security,
            config=self.config
        )

        # 8.2 Autonomous Workflow Execution (Prompt 58)
        from backend.workflows.converter import PlanToWorkflowConverter
        from backend.workflows.engine import WorkflowExecutionEngine
        self.workflow_converter = PlanToWorkflowConverter(
            capability_registry=self.skill_registry.capability_registry if hasattr(self.skill_registry, "capability_registry") else None
        )
        self.workflow_engine = WorkflowExecutionEngine(
            skill_registry=self.skill_registry,
            security_proxy=self.security,
            event_bus=self.kernel.event_bus
        )

        # 8.3 Advanced Priority Management (Prompt 59)
        from backend.priority.engine import PriorityEngine
        self.priority_engine = PriorityEngine(
            goal_engine=self.goal_engine,
            planning_engine=self.planning_engine,
            security_proxy=self.security
        )

        # 8.4 Personal Project Intelligence (Prompt 60)
        from backend.project_intelligence.engine import ProjectIntelligenceEngine
        self.project_intelligence = ProjectIntelligenceEngine(
            goal_engine=self.goal_engine,
            planning_engine=self.planning_engine,
            memory_api=self.memory
        )

        # 8.5 Autonomous Code Analysis (Prompt 61)
        from backend.code_intelligence.engine import CodeAnalysisEngine
        self.code_analysis_engine = CodeAnalysisEngine()

        # 8.6 Autonomous Code Modification (Prompt 62)
        from backend.code_modification.engine import CodeModificationEngine
        self.code_modification_engine = CodeModificationEngine(security_proxy=self.security)

        # 8.7 Intelligent Debugging (Prompt 63)
        from backend.debugging.engine import IntelligentDebuggingEngine
        self.debugging_engine = IntelligentDebuggingEngine(code_modification_engine=self.code_modification_engine)

        # 8.8 Human-in-the-Loop Autonomous Control Framework (Prompt 65)
        from backend.control.framework import AutonomousControlFramework
        self.control_framework = AutonomousControlFramework(security_proxy=self.security)

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

        # 11. Phase 5 Advanced JARVIS Experience Services (Prompts 66-74)
        from backend.notifications.service import NotificationService
        self.notification_service = NotificationService(event_bus=self.kernel.event_bus)

        from backend.visualization.service import SystemVisualizationService
        self.system_visualization = SystemVisualizationService()

        from backend.hud.service import HUDService
        self.hud_service = HUDService()

        from backend.command_center.service import DesktopCommandCenter
        self.command_center = DesktopCommandCenter(
            control_framework=self.control_framework,
            security_proxy=self.security
        )

        from backend.multimodal.orchestrator import MultimodalOrchestrator
        self.multimodal_orchestrator = MultimodalOrchestrator()

        from backend.workspace.service import WorkspaceIntelligenceService
        self.workspace_intelligence = WorkspaceIntelligenceService(memory_api=self.memory)

        from backend.ambient.service import AmbientIntelligenceService
        self.ambient_intelligence = AmbientIntelligenceService(
            notification_service=self.notification_service,
            control_framework=self.control_framework
        )

        # 12. Phase 6 Connected Intelligence Ecosystem Services (Prompts 76-85)
        from backend.connectors.registry import APIConnectorRegistry
        self.connector_registry = APIConnectorRegistry()

        from backend.smarthome.service import SmartHomeService
        self.smarthome_service = SmartHomeService()

        from backend.iot.service import IoTIntelligenceService
        self.iot_service = IoTIntelligenceService()

        from backend.hardware.service import HardwareControlService
        self.hardware_control = HardwareControlService(
            system_controller=self.tools.system_ctrl if hasattr(self.tools, "system_ctrl") else None,
            control_framework=self.control_framework
        )

        from backend.mobile.service import MobileCompanionService
        self.mobile_companion = MobileCompanionService()

        from backend.sync.service import CrossDeviceSyncEngine
        self.sync_engine = CrossDeviceSyncEngine()

        from backend.remote.service import SecureRemoteAccessGateway
        self.remote_gateway = SecureRemoteAccessGateway()

        from backend.cloud.service import PersonalCloudService
        self.personal_cloud = PersonalCloudService()

        from backend.marketplace.service import ExtensionRegistryService
        self.marketplace = ExtensionRegistryService()

        # 13. Phase 7 Scientific Intelligence & Research Lab Mode (Prompts 86-100)
        from backend.scientific.lab_mode import JarvisResearchLabMode
        self.research_lab = JarvisResearchLabMode()
