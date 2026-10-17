
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

        self.skill_registry.register(SystemSkill())
        self.skill_registry.register(MetricsSkill())
        self.skill_registry.register(PlanSkill())
        self.skill_registry.register(CodingSkill())
        self.skill_registry.register(VaultSkill())
        self.skill_registry.register(InboxSkill())
        self.skill_registry.register(TrendsSkill())
        self.skill_registry.register(BriefSkill())
        self.skill_registry.register(CloseDaySkill())
        self.skill_registry.register(ConversationSkill(brain=self.brain))

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
        logger.info("JARVIS Core is ONLINE.")

    async def _handle_voice_speak_event(self, event_type: str, data: Any):
        if self.voice_manager and isinstance(data, dict):
            text = data.get("text", "")
            if text:
                self.voice_manager.tts.speak(text)

    async def stop(self):
        self._running = False
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
