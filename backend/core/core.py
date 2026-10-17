
import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional, AsyncGenerator

from backend.core.models import (
    UserInput, CoreResponse, InputChannel, Intent, SkillResult,
    OperatingState, ExecutionState, TaskCategory
)
from backend.core.container import AppContainer

logger = logging.getLogger("JARVIS.Core")

class JarvisCore:
    def __init__(self, config: Dict[str, Any], session_id: str = "default", skills_dir: Optional[str] = None):
        self.config = config
        self.session_id = session_id
        self._running = False

        self.container = AppContainer(config, session_id, skills_dir)

        # Backward compatibility aliases
        self.kernel = self.container.kernel
        self.memory = self.container.memory
        self.brain = self.container.brain
        self.security = self.container.security
        self.agent_manager = self.container.agent_manager
        self.specialized_registry = self.container.specialized_registry
        self.multi_agent_coordinator = self.container.multi_agent_coordinator
        self.tools = self.container.tools
        self.skill_registry = self.container.skill_registry
        self.router = self.container.intent_router
        self.central_router = self.container.central_router
        self.plan_analyzer = self.container.plan_analyzer
        self.task_planner = self.container.task_planner
        self.execution_engine = self.container.execution_engine
        self.monitor_registry = self.container.monitor_registry
        self.proactive_engine = self.container.proactive_engine
        self.interaction_engine = self.container.interaction_engine
        self.orchestrator = self.container.orchestrator
        self.learning_engine = self.container.learning_engine
        self.goal_engine = getattr(self.container, "goal_engine", None)
        self.goal_decomposition_engine = getattr(self.container, "goal_decomposition_engine", None)
        self.planning_engine = getattr(self.container, "planning_engine", None)
        self.adaptive_planning = getattr(self.container, "adaptive_planning", None)
        self.workflow_converter = getattr(self.container, "workflow_converter", None)
        self.workflow_engine = getattr(self.container, "workflow_engine", None)
        self.priority_engine = getattr(self.container, "priority_engine", None)
        self.project_intelligence = getattr(self.container, "project_intelligence", None)
        self.code_analysis_engine = getattr(self.container, "code_analysis_engine", None)
        self.code_modification_engine = getattr(self.container, "code_modification_engine", None)
        self.debugging_engine = getattr(self.container, "debugging_engine", None)
        self.control_framework = getattr(self.container, "control_framework", None)
        self.notification_service = getattr(self.container, "notification_service", None)
        self.system_visualization = getattr(self.container, "system_visualization", None)
        self.hud_service = getattr(self.container, "hud_service", None)
        if self.hud_service:
            self.hud_service.core = self
        self.command_center = getattr(self.container, "command_center", None)
        if self.command_center:
            self.command_center.core = self
        self.multimodal_orchestrator = getattr(self.container, "multimodal_orchestrator", None)
        if self.multimodal_orchestrator:
            self.multimodal_orchestrator.core = self
        self.workspace_intelligence = getattr(self.container, "workspace_intelligence", None)
        self.ambient_intelligence = getattr(self.container, "ambient_intelligence", None)
        self.connector_registry = getattr(self.container, "connector_registry", None)
        self.smarthome_service = getattr(self.container, "smarthome_service", None)
        self.iot_service = getattr(self.container, "iot_service", None)
        self.hardware_control = getattr(self.container, "hardware_control", None)
        self.mobile_companion = getattr(self.container, "mobile_companion", None)
        self.sync_engine = getattr(self.container, "sync_engine", None)
        self.remote_gateway = getattr(self.container, "remote_gateway", None)
        self.personal_cloud = getattr(self.container, "personal_cloud", None)
        self.marketplace = getattr(self.container, "marketplace", None)
        self.research_lab = getattr(self.container, "research_lab", None)
        if self.research_lab:
            self.research_lab.core = self
        self.voice_manager = None
        self.plugin_manager = None
        self.diagnostics_engine = None

        # Register default skills
        from backend.skills.system_skill import SystemSkill
        from backend.skills.metrics_skill import MetricsSkill
        from backend.skills.plan_skill import PlanSkill
        from backend.skills.coding_skill import CodingSkill
        from backend.skills.vault_skill import VaultSkill
        from backend.skills.inbox_skill import InboxSkill
        from backend.skills.trends_skill import TrendsSkill
        from backend.skills.brief_skill import BriefSkill
        from backend.skills.close_day_skill import CloseDaySkill
        from backend.skills.conversation_skill import ConversationSkill
        from backend.skills.goal_skill import GoalSkill

        self.skill_registry.register(SystemSkill())
        self.skill_registry.register(MetricsSkill())
        self.skill_registry.register(PlanSkill(
            planner=self.task_planner,
            planning_engine=self.planning_engine,
            adaptive_planning=self.adaptive_planning
        ))
        self.skill_registry.register(CodingSkill())
        self.skill_registry.register(VaultSkill())
        self.skill_registry.register(InboxSkill())
        self.skill_registry.register(TrendsSkill())
        self.skill_registry.register(BriefSkill())
        self.skill_registry.register(CloseDaySkill())
        self.skill_registry.register(ConversationSkill(brain=self.brain))
        self.skill_registry.register(GoalSkill(
            engine=self.goal_engine,
            decomposition_engine=self.goal_decomposition_engine
        ))

    def _handle_agent_state_update(self, agent_id: str, state: str, details: Dict[str, Any]):
        pass

    async def start(self):
        if self._running:
            return
        self._running = True
        logger.info("Booting JARVIS Core Operating System...")
        await self.kernel.start()
        self.kernel.scheduler.set_core_executor(self.process_input)
        self.kernel.scheduler.set_event_bus(self.kernel.event_bus)
        await self.kernel.event_bus.subscribe("user_input_request", self._handle_event_bus_input)
        await self.kernel.event_bus.subscribe("voice_speak_request", self._handle_voice_speak_event)
        if self.proactive_engine:
            await self.proactive_engine.start()
        if hasattr(self, 'learning_engine') and self.learning_engine:
            await self.learning_engine.start()
        if self.adaptive_planning and hasattr(self.adaptive_planning, "start_monitoring"):
            try:
                self.adaptive_planning.start_monitoring()
            except Exception as e:
                logger.warning(f"Failed to start adaptive planning monitoring: {e}")
        logger.info("JARVIS Core is ONLINE.")

    async def _handle_voice_speak_event(self, event_type: str, data: Any):
        if self.voice_manager and isinstance(data, dict):
            text = data.get("text", "")
            if text:
                self.voice_manager.tts.speak(text)

    async def stop(self):
        self._running = False
        if self.adaptive_planning and hasattr(self.adaptive_planning, "stop_monitoring"):
            try:
                self.adaptive_planning.stop_monitoring()
            except Exception as e:
                logger.warning(f"Failed to stop adaptive planning monitoring: {e}")
        if self.proactive_engine:
            await self.proactive_engine.stop()
        if self.plugin_manager:
            self.plugin_manager.stop()
        await self.kernel.stop()
        self.memory.close()
        if self.voice_manager:
            self.voice_manager.stop()
        logger.info("JARVIS Core offline.")

    def cancel(self):
        if self.execution_engine:
            self.execution_engine.cancel()
        if self.orchestrator:
            self.orchestrator.cancel()
        if self.multi_agent_coordinator:
            self.multi_agent_coordinator.cancel()
        if self.agent_manager:
            self.agent_manager.cancel()

    async def process_input(self, user_input: UserInput, execution_context: Optional[Any] = None) -> CoreResponse:
        result = await self.orchestrator.process_request(user_input)
        await self.kernel.event_bus.publish("command_executed", {
            "request_id": user_input.request_id,
            "skill": result.skill,
            "status": result.status,
            "state": result.state.value if hasattr(result.state, "value") else str(result.state),
            "execution_time_ms": result.execution_time_ms
        })
        intent_obj = None
        if result.intent:
            itype = result.intent.get("intent_type") or result.intent.get("type", "unknown")
            try:
                intent_obj = Intent(
                    intent_type=itype,
                    skill_name=result.skill,
                    action=result.intent.get("action", ""),
                    confidence=result.intent.get("confidence", 1.0),
                    raw_input=user_input.content
                )
            except Exception:
                pass
        return CoreResponse(
            text=result.response,
            channel=user_input.channel,
            intent=intent_obj,
            data=result.to_dict(),
            execution_time_ms=result.execution_time_ms,
            request_id=user_input.request_id,
            state=OperatingState.SUCCESS if result.status == "success" else OperatingState.FAILED
        )

    async def process_stream(self, user_input: UserInput) -> AsyncGenerator[Dict[str, Any], None]:
        start_time = time.time()
        intent = self.router.route(user_input)
        yield {"type": "intent_routed", "data": {"skill": intent.skill_name, "action": intent.action, "confidence": intent.confidence}}
        if intent.skill_name == "conversation":
            full_output = ""
            skill = self.skill_registry.get_skill("conversation")
            context = {"session_id": user_input.session_id, "channel": user_input.channel, "memory": self.memory}
            if skill and hasattr(skill, "execute_stream"):
                for chunk in skill.execute_stream(intent, context):
                    full_output += chunk
                    yield {"type": "chat_stream", "data": {"chunk": chunk}}
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            yield {"type": "chat_complete", "data": {"role": "assistant", "content": full_output, "skill": "conversation", "action": "chat", "execution_time_ms": elapsed_ms}}
        else:
            result = await self.central_router.execute(user_input)
            yield {"type": "chat_stream", "data": {"chunk": result.response}}
            yield {"type": "chat_complete", "data": {"role": "assistant", "content": result.response, "skill": result.skill, "action": result.actions[0] if result.actions else "", "execution_time_ms": result.execution_time_ms}}

    async def _handle_event_bus_input(self, event_type: str, data: Any):
        if isinstance(data, dict):
            content = data.get("content") or data.get("message", "")
            channel = InputChannel(data.get("channel", "text"))
            user_in = UserInput(content=content, channel=channel, metadata=data)
            await self.process_input(user_in)

    # ─────────────────────────────────────────────────────────────
    # Application-Level Long-Horizon & Adaptive Planning Methods
    # ─────────────────────────────────────────────────────────────

    def create_long_horizon_plan(
        self,
        goal_id: str,
        title: Optional[str] = None,
        author: str = "User",
        deadline: Optional[str] = None,
    ):
        """Creates and persists a long-horizon strategic plan for an approved goal."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.create_plan(goal_id=goal_id, title=title, author=author, deadline=deadline)

    def get_plan(self, plan_id: str):
        """Retrieves a strategic plan by ID."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.get_plan(plan_id)

    def list_plans(self, status: Optional[str] = None):
        """Lists strategic plans, optionally filtered by status."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.list_plans(status=status)

    def submit_plan_for_approval(self, plan_id: str, author: str = "User"):
        """Submits a draft plan for human review and approval."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.submit_for_approval(plan_id=plan_id, author=author)

    def approve_plan(self, plan_id: str, reviewer: str = "User"):
        """Approves a proposed strategic plan."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.approve_plan(plan_id=plan_id, reviewer=reviewer)

    def reject_plan(self, plan_id: str, reviewer: str = "User", reason: str = ""):
        """Rejects a proposed strategic plan."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.reject_plan(plan_id=plan_id, reviewer=reviewer, reason=reason)

    def activate_plan(self, plan_id: str, user: str = "User"):
        """Activates an approved strategic plan."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.activate_plan(plan_id=plan_id, user=user)

    def get_critical_path(self, plan_id: str):
        """Computes and returns the critical path for a strategic plan."""
        if not self.planning_engine:
            raise RuntimeError("LongHorizonPlanningEngine is not initialized.")
        return self.planning_engine.get_critical_path(plan_id=plan_id)

    def assess_plan_adaptation(self, trigger):
        """Evaluates whether an active plan requires adaptation."""
        if not self.adaptive_planning:
            raise RuntimeError("AdaptivePlanningSubsystem is not initialized.")
        return self.adaptive_planning.process_trigger(trigger)

    def propose_plan_revision(self, plan_id: str, author: str = "JARVIS", reason: str = ""):
        """Generates a candidate revision and structural diff without mutating the baseline."""
        if not self.adaptive_planning:
            raise RuntimeError("AdaptivePlanningSubsystem is not initialized.")
        from backend.planning.adaptive_planning import PlanStructuralDiff
        baseline = self.get_plan(plan_id)
        candidate = self.adaptive_planning.propose_revision(plan_id=plan_id, author=author, reason=reason)
        diff = PlanStructuralDiff.compute(baseline=baseline, candidate=candidate)
        return candidate, diff

    def approve_plan_revision(self, plan_id: str, reviewer: str = "User"):
        """Approves a proposed revision and atomically updates the baseline."""
        if not self.adaptive_planning:
            raise RuntimeError("AdaptivePlanningSubsystem is not initialized.")
        return self.adaptive_planning.approve_revision(plan_id=plan_id, reviewer=reviewer)

    def reject_plan_revision(self, plan_id: str, reviewer: str = "User", reason: str = ""):
        """Rejects a proposed revision, keeping the existing baseline intact."""
        if not self.adaptive_planning:
            raise RuntimeError("AdaptivePlanningSubsystem is not initialized.")
        return self.adaptive_planning.reject_revision(plan_id=plan_id, reviewer=reviewer, reason=reason)

    def get_plan_revision_history(self, plan_id: str):
        """Retrieves immutable revision history snapshots for a plan."""
        if not self.adaptive_planning:
            raise RuntimeError("AdaptivePlanningSubsystem is not initialized.")
        return self.adaptive_planning.get_revision_history(plan_id=plan_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Workflow Execution APIs (Prompt 58)
    # ─────────────────────────────────────────────────────────────────────────
    def convert_plan_to_workflow(self, plan_id: str):
        """Converts an approved long-horizon plan into an executable workflow without executing it."""
        if not self.workflow_converter:
            raise RuntimeError("Workflow converter is not configured.")
        plan = self.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan '{plan_id}' does not exist.")
        return self.workflow_converter.convert(plan)

    def authorize_workflow_execution(self, execution, authorizer: str = "User"):
        """Validates execution authorization against SecurityProxy."""
        if not self.workflow_engine:
            raise RuntimeError("Workflow execution engine is not configured.")
        return self.workflow_engine.authorize_execution(execution, authorizer=authorizer)

    def execute_workflow(self, workflow, execution):
        """Executes an authorized workflow."""
        if not self.workflow_engine:
            raise RuntimeError("Workflow execution engine is not configured.")
        return self.workflow_engine.execute_workflow(workflow, execution)

    def cancel_workflow_execution(self, execution_id: str, reason: str = "User requested cancellation"):
        """Signals cancellation to an active workflow execution."""
        if not self.workflow_engine:
            raise RuntimeError("Workflow execution engine is not configured.")
        return self.workflow_engine.cancel_execution(execution_id, reason=reason)

    # ─────────────────────────────────────────────────────────────────────────
    # Priority Intelligence APIs (Prompt 59)
    # ─────────────────────────────────────────────────────────────────────────
    def evaluate_item_priority(self, goal):
        """Calculates an explainable multi-factor priority score."""
        if not self.priority_engine:
            raise RuntimeError("Priority engine is not configured.")
        return self.priority_engine.evaluate_goal_priority(goal)

    def set_priority_override(self, item_id: str, item_type, level, reason: str, author: str = "User"):
        """Records an explicit human override fixing the priority level."""
        if not self.priority_engine:
            raise RuntimeError("Priority engine is not configured.")
        return self.priority_engine.set_user_override(
            item_id=item_id,
            item_type=item_type,
            level=level,
            reason=reason,
            author=author,
        )

    def get_priority_recommendations(self):
        """Generates ranked scheduling recommendations across active goals and tasks."""
        if not self.priority_engine:
            raise RuntimeError("Priority engine is not configured.")
        return self.priority_engine.get_schedule_recommendations()

    # ─────────────────────────────────────────────────────────────────────────
    # Project Intelligence APIs (Prompt 60)
    # ─────────────────────────────────────────────────────────────────────────
    def register_personal_project(self, name: str, description: str = "", repository_path: str = None, linked_goal_ids=None):
        """Registers a personal engineering project with linked goal provenance."""
        if not self.project_intelligence:
            raise RuntimeError("Project intelligence is not configured.")
        return self.project_intelligence.register_project(
            name=name,
            description=description,
            repository_path=repository_path,
            linked_goal_ids=linked_goal_ids,
        )

    def get_project_status(self, project_id: str):
        """Synthesizes structured project status, blockers, and architectural decisions."""
        if not self.project_intelligence:
            raise RuntimeError("Project intelligence is not configured.")
        return self.project_intelligence.analyze_project_status(project_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Code Analysis APIs (Prompt 61)
    # ─────────────────────────────────────────────────────────────────────────
    def analyze_codebase(self, root_dir: str, max_files: int = 50):
        """Executes autonomous read-only static analysis over code files."""
        if not self.code_analysis_engine:
            raise RuntimeError("Code analysis engine is not configured.")
        return self.code_analysis_engine.analyze_directory(root_dir=root_dir, max_files=max_files)

    # ─────────────────────────────────────────────────────────────────────────
    # Code Modification APIs (Prompt 62)
    # ─────────────────────────────────────────────────────────────────────────
    def propose_code_patch(self, file_path: str, new_content: str, rationale: str, author: str = "JARVIS"):
        """Validates syntax and creates a unified diff patch proposal."""
        if not self.code_modification_engine:
            raise RuntimeError("Code modification engine is not configured.")
        return self.code_modification_engine.propose_patch(
            file_path=file_path,
            new_content=new_content,
            rationale=rationale,
            author=author,
        )

    def approve_code_patch(self, proposal_id: str, approver: str = "User"):
        """Authorizes a patch proposal via SecurityProxy."""
        if not self.code_modification_engine:
            raise RuntimeError("Code modification engine is not configured.")
        return self.code_modification_engine.approve_patch(proposal_id=proposal_id, approver=approver)

    def apply_code_patch(self, proposal_id: str):
        """Applies an authorized patch to disk, preserving rollback snapshot."""
        if not self.code_modification_engine:
            raise RuntimeError("Code modification engine is not configured.")
        return self.code_modification_engine.apply_patch(proposal_id=proposal_id)

    def rollback_code_patch(self, proposal_id: str):
        """Restores file to its pre-modification state."""
        if not self.code_modification_engine:
            raise RuntimeError("Code modification engine is not configured.")
        return self.code_modification_engine.rollback_patch(proposal_id=proposal_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Intelligent Debugging APIs (Prompt 63)
    # ─────────────────────────────────────────────────────────────────────────
    def diagnose_error(self, exc: Exception, affected_component: str = None, context: dict = None):
        """Analyzes an exception, sanitizes traces, and formulates evidence-backed hypotheses."""
        if not self.debugging_engine:
            raise RuntimeError("Debugging engine is not configured.")
        return self.debugging_engine.diagnose_exception(
            exc=exc,
            affected_component=affected_component,
            context=context,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Continuous Improvement APIs (Prompt 64)
    # ─────────────────────────────────────────────────────────────────────────
    def get_improvement_recommendations(self):
        """Synthesizes actionable improvement recommendations from observed telemetry and learnings."""
        if not self.learning_engine:
            raise RuntimeError("Learning engine is not configured.")
        return self.learning_engine.generate_improvement_recommendations()

    # ─────────────────────────────────────────────────────────────────────────
    # Human-in-the-Loop Autonomous Control Framework APIs (Prompt 65)
    # ─────────────────────────────────────────────────────────────────────────
    def request_autonomous_action_approval(
        self,
        action_type: str,
        subsystem: str,
        risk_tier,
        description: str,
        parameters: dict,
        target_resource: str = None,
        timeout_seconds: float = 300.0,
    ):
        """Requests unified human approval bound to a cryptographic payload hash."""
        if not self.control_framework:
            raise RuntimeError("Control framework is not configured.")
        return self.control_framework.request_approval(
            action_type=action_type,
            subsystem=subsystem,
            risk_tier=risk_tier,
            description=description,
            parameters=parameters,
            target_resource=target_resource,
            timeout_seconds=timeout_seconds,
        )

    def approve_autonomous_action(self, request_id: str, approver: str = "User"):
        """Approves a pending unified approval request."""
        if not self.control_framework:
            raise RuntimeError("Control framework is not configured.")
        return self.control_framework.approve_request(request_id=request_id, approver=approver)

    def trigger_emergency_stop(self, reason: str = "Operator triggered emergency stop"):
        """Immediately engages global emergency stop halting autonomous work."""
        if not self.control_framework:
            raise RuntimeError("Control framework is not configured.")
        self.control_framework.trigger_emergency_stop(reason=reason)

    def clear_emergency_stop(self, authorizer: str = "User"):
        """Disengages global emergency stop."""
        if not self.control_framework:
            raise RuntimeError("Control framework is not configured.")
        self.control_framework.clear_emergency_stop(authorizer=authorizer)
