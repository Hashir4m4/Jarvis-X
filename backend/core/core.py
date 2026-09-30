import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional, AsyncGenerator

from backend.core.models import (
    UserInput, CoreResponse, InputChannel, Intent, SkillResult,
    OperatingState, ExecutionState, TaskCategory
)
from backend.router.intent_router import IntentRouter
from backend.router.central_router import CentralRouter
from backend.router.tool_registry import ToolRegistry
from backend.router.context import ExecutionContext
from backend.skills.registry import SkillRegistry
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
from backend.agents.agent_manager import AgentManager
from backend.agents.planner import Planner
from backend.automation.security_proxy import SecurityProxy
from backend.kernel.kernel import JarvisKernel
from backend.brain import Brain
from backend.memory_manager import MemoryManager

logger = logging.getLogger("JARVIS.Core")


class JarvisCore:
    """
    JARVIS OS Core Operating Layer.
    Central orchestrator unifying all inputs (Text, Voice, Scheduled, UI),
    Multi-Agent Swarms (Planner, Coder, Reviewer, Executor),
    Central Routing, Skills Registry, Memory, and Subsystem Execution.
    """

    def __init__(self, config: Dict[str, Any], session_id: str = "default", skills_dir: Optional[str] = None):
        self.config = config
        self.session_id = session_id

        # 1. Kernel (Async Event Loop, Task Manager, Scheduler)
        self.kernel = JarvisKernel(config)

        # 2. Memory & Brain (Reused existing implementations)
        self.memory = MemoryManager(config, session_id=session_id)
        self.brain = Brain(config, session_id=session_id)
        self.security = SecurityProxy(self.config)

        # 3. Multi-Agent System (Planner, Coder, Reviewer, Executor)
        self.agent_manager = AgentManager(
            llm=self.brain.llm,
            security=self.security,
            working_dir=".",
            state_callback=self._handle_agent_state_update
        )

        # 3b. Controlled Specialized Multi-Agent Intelligence System
        from backend.agents.agent_registry import AgentRegistry
        from backend.agents.multi_agent_coordinator import MultiAgentCoordinator
        from backend.agents.specialized import (
            ResearchAgent,
            CodingAgent,
            PlanningAgent,
            AnalysisAgent,
            SystemAgent,
            ProductivityAgent
        )
        self.specialized_registry = AgentRegistry()
        self.specialized_registry.register(ResearchAgent())
        self.specialized_registry.register(CodingAgent())
        self.specialized_registry.register(PlanningAgent())
        self.specialized_registry.register(AnalysisAgent())
        self.specialized_registry.register(SystemAgent())
        self.specialized_registry.register(ProductivityAgent())

        self.multi_agent_coordinator = MultiAgentCoordinator(
            registry=self.specialized_registry,
            event_bus=self.kernel.event_bus,
            security=self.security,
            tools=None,
            model_router=None,
            config=self.config
        )

        # 4. Tool Registry (incorporating multi-agent swarm & scheduler)
        self.tools = ToolRegistry(agent_manager=self.agent_manager)
        self.tools.register_scheduler_tools(self.kernel.scheduler)
        self.multi_agent_coordinator.tools = self.tools

        # 5. Skill Registry & Automatic Discovery
        if skills_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
            candidate_skills = os.path.join(base_dir, "skills")
            skills_dir = candidate_skills if os.path.isdir(candidate_skills) else None

        self.skill_registry = SkillRegistry(skills_dir=skills_dir)
        self._register_default_skills()

        # 6. Intent Router, Central Router, and Intelligence Orchestrator
        self.router = IntentRouter(skill_registry=self.skill_registry)
        self.central_router = CentralRouter(
            skill_registry=self.skill_registry,
            intent_router=self.router,
            memory_api=self.memory,
            tool_registry=self.tools
        )

        # 3c. Autonomous Task Planning & Controlled Execution Engine
        from backend.planning import PlanAnalyzer, TaskPlanner, ExecutionEngine
        self.plan_analyzer = PlanAnalyzer(
            skill_registry=self.skill_registry if hasattr(self, "skill_registry") else None,
            tool_registry=self.tools,
            agent_registry=self.specialized_registry
        )
        self.task_planner = TaskPlanner(
            analyzer=self.plan_analyzer,
            config=self.config
        )
        self.execution_engine = ExecutionEngine(
            analyzer=self.plan_analyzer,
            skill_registry=self.skill_registry if hasattr(self, "skill_registry") else None,
            tool_registry=self.tools,
            agent_coordinator=self.multi_agent_coordinator,
            security_proxy=self.security,
            event_bus=self.kernel.event_bus,
            config=self.config
        )

        # 3d. Controlled Proactive Intelligence and Event Monitoring System
        from backend.proactive import ProactiveEngine, MonitorRegistry
        self.monitor_registry = MonitorRegistry(
            event_bus=self.kernel.event_bus,
            system_controller=self.tools.system_ctrl if hasattr(self.tools, "system_ctrl") else None
        )
        self.proactive_engine = ProactiveEngine(
            event_bus=self.kernel.event_bus,
            monitor_registry=self.monitor_registry,
            config=self.config
        )

        from backend.orchestrator.orchestrator import JarvisOrchestrator

        # 3e. Personality & Adaptive Interaction System
        from backend.interaction import InteractionEngine
        self.interaction_engine = InteractionEngine(config=self.config)

        self.orchestrator = JarvisOrchestrator(
            skill_registry=self.skill_registry,
            intent_router=self.router,
            memory_api=self.memory,
            tool_registry=self.tools,
            agent_manager=self.agent_manager,
            security_proxy=self.security,
            event_bus=self.kernel.event_bus,
            llm_provider=getattr(self.brain.llm, "provider", None) if hasattr(self, "brain") and hasattr(self.brain, "llm") else None,
            config=self.config,
            multi_agent_coordinator=self.multi_agent_coordinator,
            task_planner=self.task_planner,
            execution_engine=self.execution_engine,
            interaction_engine=self.interaction_engine,
        )
        self.multi_agent_coordinator.model_router = self.orchestrator.model_router
        self.plan_analyzer.skill_registry = self.skill_registry
        self.execution_engine.skill_registry = self.skill_registry

        # 3f. Self-Diagnostics, Health Monitoring & Safe Self-Healing System
        from backend.diagnostics import DiagnosticsEngine
        self.diagnostics_engine = DiagnosticsEngine(
            config=self.config,
            orchestrator=self.orchestrator,
            memory_manager=self.memory,
            security_proxy=self.security,
            execution_engine=self.execution_engine,
            event_bus=self.kernel.event_bus,
            # voice_manager, cloud_manager, knowledge_base wired after boot
        )
        # Inject into orchestrator so DiagnosticSkill context has access
        self.orchestrator.diagnostics_engine = self.diagnostics_engine

        # 7. Voice Interface (Unified Provider Architecture)
        from backend.voice.voice_manager import VoiceManager
        self.voice_manager = VoiceManager(
            config=self.config,
            router=self.orchestrator,
            state_callback=self._handle_voice_state_update
        )

        # 8. Safe Plugin and Extensibility Ecosystem
        from backend.plugins import PluginManager
        self.plugin_manager = PluginManager(
            plugins_dir=os.path.join(os.path.dirname(__file__), "..", "plugins"),
            core_config=self.config,
            security_proxy=self.security,
            event_bus=self.kernel.event_bus,
            memory_api=self.memory,
            skill_registry=self.skill_registry,
            tool_registry=self.tools,
            agent_registry=self.agent_manager
        )
        self.plugin_manager.discover_and_load()

        self._running = False
        logger.info(f"JARVIS Core initialized with Intelligence Orchestrator, Voice & Extensibility Ecosystem. Session: '{session_id}'")

    def _register_default_skills(self):
        """Discovers and registers built-in skills."""
        # 1. System Skill
        self.skill_registry.register(SystemSkill())

        # 2. Metrics Skill
        self.skill_registry.register(MetricsSkill())

        # 3. Plan Skill (reuses Planner agent)
        planner = Planner(self.config) if self.config else None
        self.skill_registry.register(PlanSkill(planner=planner))

        # 4. Multi-Agent Coding Skill (Planner -> Coder -> Reviewer -> Executor)
        self.skill_registry.register(CodingSkill(agent_manager=self.agent_manager))

        # 5. Vault Skill (reuses SQLite user preferences)
        self.skill_registry.register(VaultSkill(sqlite_manager=self.memory.sqlite))

        # 6. Inbox Skill (reuses SQLite conversation store)
        self.skill_registry.register(InboxSkill(sqlite_manager=self.memory.sqlite))

        # 7. Trends Skill (reuses SQLite history analytics)
        self.skill_registry.register(TrendsSkill(sqlite_manager=self.memory.sqlite))

        # 8. OS Daily Workflow Skills (Morning Brief & Close The Day)
        self.skill_registry.register(BriefSkill(sqlite_manager=self.memory.sqlite))
        self.skill_registry.register(CloseDaySkill(sqlite_manager=self.memory.sqlite))

        # 9. Fallback Conversation Skill (Brain + LLM synthesis)
        self.skill_registry.register(ConversationSkill(self.brain))
        
        # 10. Memory Skill
        from backend.skills.memory_skill import MemorySkill
        self.skill_registry.register(MemorySkill())

        # 11. Desktop Skill (Safe Computer Control)
        from backend.skills.desktop_skill import DesktopSkill
        self.desktop_skill = DesktopSkill(security_proxy=self.security)
        self.skill_registry.register(self.desktop_skill)

        # 12. Screen Vision & Computer Understanding Skill
        from backend.skills.screen_vision_skill import ScreenVisionSkill
        self.screen_vision_skill = ScreenVisionSkill()
        self.skill_registry.register(self.screen_vision_skill)

        # 13. Self-Diagnostics Skill
        from backend.diagnostics import DiagnosticSkill
        self.diagnostic_skill = DiagnosticSkill(
            diagnostics_engine=self.diagnostics_engine if hasattr(self, "diagnostics_engine") else None
        )
        self.skill_registry.register(self.diagnostic_skill)

    def emergency_stop(self):
        """Halts all automation immediately across DesktopSkill, Orchestrator, ExecutionEngine, and Agents."""
        logger.critical("[JARVIS CORE] Emergency Stop invoked!")
        if hasattr(self, "execution_engine") and self.execution_engine:
            self.execution_engine.emergency_stop()
        if hasattr(self, "desktop_skill") and self.desktop_skill:
            self.desktop_skill.emergency_stop()
        self.cancel()

    def _handle_agent_state_update(self, payload: Dict[str, Any]):
        """Callback from AgentManager emitting state telemetry to Kernel EventBus & HUD."""
        logger.debug(f"[HUD Telemetry] Agent {payload.get('agent')} -> {payload.get('state')}")
        if self._running and self.kernel and self.kernel.event_bus:
            # Schedule task on event bus to publish state
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.kernel.event_bus.publish("agent_status", payload))
            except Exception:
                pass

    def _handle_voice_state_update(self, payload: Dict[str, Any]):
        """Callback from VoiceManager emitting voice state telemetry to Kernel EventBus & HUD."""
        logger.debug(f"[HUD Telemetry] Voice State -> {payload.get('state')}")
        if self._running and self.kernel and self.kernel.event_bus:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.kernel.event_bus.publish("voice_state", payload))
            except Exception:
                pass

    async def start(self):
        """Boots the entire OS Core and background services."""
        if self._running:
            return

        self._running = True
        logger.info("Booting JARVIS Core Operating System...")

        # Boot Kernel services
        await self.kernel.start()

        # Wire Scheduler through JARVIS Core input pipeline & EventBus
        self.kernel.scheduler.set_core_executor(self.process_input)
        self.kernel.scheduler.set_event_bus(self.kernel.event_bus)

        # Wire event bus to handle user input requests if published
        await self.kernel.event_bus.subscribe("user_input_request", self._handle_event_bus_input)
        await self.kernel.event_bus.subscribe("voice_speak_request", self._handle_voice_speak_event)

        # Start Proactive Intelligence Engine
        if hasattr(self, "proactive_engine") and self.proactive_engine:
            await self.proactive_engine.start()

        # Start Self-Diagnostics Health Monitoring (EventBus subscriptions)
        if hasattr(self, "diagnostics_engine") and self.diagnostics_engine:
            await self.diagnostics_engine.start()
            # Run startup diagnostics (non-blocking — failures are reported, not fatal)
            try:
                startup_report = await self.diagnostics_engine.run_startup_diagnostics()
                logger.info(
                    f"[JARVIS] Startup diagnostics: {startup_report.overall_status.value} "
                    f"({startup_report.healthy_count()}/{len(startup_report.results)} healthy)"
                )
                # Publish HUD payload
                await self.kernel.event_bus.publish(
                    "health_status_changed",
                    startup_report.to_hud_payload()
                )
            except Exception as diag_err:
                logger.warning(f"[JARVIS] Startup diagnostics error (non-fatal): {diag_err}")

        logger.info("JARVIS Core is ONLINE.")

    async def _handle_voice_speak_event(self, event_type: str, data: Any):
        """Pipes scheduled speech notifications to the TTS system."""
        if self.voice_manager and isinstance(data, dict):
            text = data.get("text", "")
            if text:
                self.voice_manager.tts.speak(text)

    async def stop(self):
        """Gracefully shuts down the OS Core."""
        self._running = False
        if hasattr(self, "proactive_engine") and self.proactive_engine:
            await self.proactive_engine.stop()
        if hasattr(self, "diagnostics_engine") and self.diagnostics_engine:
            await self.diagnostics_engine.stop()
        if hasattr(self, "plugin_manager") and self.plugin_manager:
            self.plugin_manager.stop()
        await self.kernel.stop()
        self.memory.close()
        if self.voice_manager:
            self.voice_manager.stop()
        logger.info("JARVIS Core offline.")

    def cancel(self):
        """Cancels any running orchestration or multi-agent tasks."""
        if hasattr(self, "execution_engine") and self.execution_engine:
            self.execution_engine.cancel()
        if hasattr(self, "orchestrator") and self.orchestrator:
            self.orchestrator.cancel()
        if hasattr(self, "multi_agent_coordinator") and self.multi_agent_coordinator:
            self.multi_agent_coordinator.cancel()
        if self.agent_manager:
            self.agent_manager.cancel()

    async def process_input(self, user_input: UserInput, execution_context: Optional[ExecutionContext] = None) -> CoreResponse:
        """
        Processes an incoming user request through the Central Intelligence Orchestrator:
        INPUT -> CONTEXT -> RETRIEVAL -> UNDERSTANDING -> STRATEGY -> PERMISSIONS -> EXECUTION -> VERIFICATION -> MEMORY -> RESPONSE
        """
        result = await self.orchestrator.process_request(user_input)

        # Publish event on kernel event bus
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
        """
        Streaming pipeline for real-time WebSocket / HUD updates.
        """
        start_time = time.time()
        intent = self.router.route(user_input)

        yield {
            "type": "intent_routed",
            "data": {
                "skill": intent.skill_name,
                "action": intent.action,
                "confidence": intent.confidence
            }
        }

        # If it's a conversational query, stream from LLM
        if intent.skill_name == "conversation":
            full_output = ""
            skill = self.skill_registry.get_skill("conversation")
            context = {"session_id": user_input.session_id, "channel": user_input.channel, "memory": self.memory}
            if skill and hasattr(skill, "execute_stream"):
                for chunk in skill.execute_stream(intent, context):
                    full_output += chunk
                    yield {
                        "type": "chat_stream",
                        "data": {"chunk": chunk}
                    }
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            yield {
                "type": "chat_complete",
                "data": {
                    "role": "assistant",
                    "content": full_output,
                    "skill": "conversation",
                    "action": "chat",
                    "execution_time_ms": elapsed_ms
                }
            }
        else:
            # Deterministic / Tool Skills executed via CentralRouter
            result = await self.central_router.execute(user_input)
            yield {
                "type": "chat_stream",
                "data": {"chunk": result.response}
            }
            yield {
                "type": "chat_complete",
                "data": {
                    "role": "assistant",
                    "content": result.response,
                    "skill": result.skill,
                    "action": result.actions[0] if result.actions else "",
                    "execution_time_ms": result.execution_time_ms
                }
            }

    async def _handle_event_bus_input(self, event_type: str, data: Any):
        """Processes input arriving asynchronously through the EventBus."""
        if isinstance(data, dict):
            content = data.get("content") or data.get("message", "")
            channel = InputChannel(data.get("channel", "text"))
            user_in = UserInput(content=content, channel=channel, metadata=data)
            await self.process_input(user_in)
