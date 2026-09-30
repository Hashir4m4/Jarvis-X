import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, AsyncGenerator

from backend.core.models import (
    UserInput, InputChannel, Intent, CoreResponse, OperatingState,
    ExecutionState, TaskCategory, JarvisError, ErrorCategory, SkillResult, IntentType
)
from backend.router.context import ExecutionContext, RouterExecutionResult
from backend.router.intent_router import IntentRouter
from backend.skills.registry import SkillRegistry
from backend.router.tool_registry import ToolRegistry
from backend.agents.agent_manager import AgentManager
from backend.automation.security_proxy import SecurityProxy, PermissionLevel
from backend.memory.memory_api import MemoryAPI
from backend.kernel.event_bus import EventBus
from backend.core.capability_detector import CapabilityDetector, CapabilityState, AIMode
from backend.llm.local_models import LocalModelConfig
from backend.llm.model_router import (
    ModelRouter, ModelSelectionRequest, ModelSelectionResult,
    PrivacyPolicy, UserRoutingPreference, RoutingStatus,
    classify_complexity, detect_privacy_level,
)
from backend.memory.context_manager import ContextManager
from .decision_engine import DecisionEngine

logger = logging.getLogger("JARVIS.Orchestrator")


class JarvisOrchestrator:
    """
    Central JARVIS Intelligence Orchestrator.
    Highest-level intelligence coordination layer responsible for managing how
    JARVIS processes every request across Text, Voice, HUD, Scheduler, and API sources,
    with robust offline intelligence awareness and dynamic capability detection.
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        intent_router: IntentRouter,
        memory_api: Optional[MemoryAPI] = None,
        tool_registry: Optional[ToolRegistry] = None,
        agent_manager: Optional[AgentManager] = None,
        security_proxy: Optional[SecurityProxy] = None,
        event_bus: Optional[EventBus] = None,
        llm_provider: Optional[Any] = None,
        cloud_manager: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        multi_agent_coordinator: Optional[Any] = None,
        task_planner: Optional[Any] = None,
        execution_engine: Optional[Any] = None,
        interaction_engine: Optional[Any] = None,
        diagnostics_engine: Optional[Any] = None,
    ):
        self.skill_registry = skill_registry
        self.intent_router = intent_router
        self.memory = memory_api
        self.tools = tool_registry
        self.agent_manager = agent_manager
        self.coordinator = multi_agent_coordinator
        self.planner = task_planner
        self.execution_engine = execution_engine
        self.security = security_proxy or SecurityProxy(config)
        self.event_bus = event_bus
        self.llm_provider = llm_provider
        self.config = config or {}

        from backend.llm.cloud_manager import CloudProviderManager
        self.cloud_manager = cloud_manager or CloudProviderManager(self.config)

        self._cancelled = False
        self.current_state: ExecutionState = ExecutionState.IDLE
        self.decision_engine = DecisionEngine()
        self.capability_detector = CapabilityDetector(cache_ttl_seconds=15.0)
        self.local_model_config = LocalModelConfig.from_config(self.config)
        self.model_router = ModelRouter(self.config)
        self.context_manager = ContextManager(self.config)

        # Personality & Adaptive Interaction System
        # Initialized here if not injected; used throughout process_request.
        if interaction_engine is not None:
            self.interaction_engine = interaction_engine
        else:
            try:
                from backend.interaction import InteractionEngine
                self.interaction_engine = InteractionEngine(config=self.config)
            except Exception as _ie_err:
                logger.warning(f"[ORCHESTRATOR] InteractionEngine unavailable (non-fatal): {_ie_err}")
                self.interaction_engine = None

        # Self-Diagnostics Engine (injected; also settable via attribute post-init)
        self.diagnostics_engine = diagnostics_engine

    def cancel(self):
        """Signals active orchestration pipelines to cancel execution immediately."""
        self._cancelled = True
        if self.execution_engine:
            self.execution_engine.cancel()
        if self.coordinator:
            self.coordinator.cancel()
        if self.agent_manager:
            self.agent_manager.cancel()
        logger.warning("[ORCHESTRATOR] Execution cancellation requested.")

    def pause(self):
        """Pauses active execution engine tasks."""
        if self.execution_engine:
            self.execution_engine.pause()

    def resume(self):
        """Resumes active execution engine tasks."""
        if self.execution_engine:
            self.execution_engine.resume()

    async def execute(self, user_input: UserInput, execution_context: Optional[ExecutionContext] = None) -> RouterExecutionResult:
        """Alias for process_request for drop-in CentralRouter compatibility."""
        return await self.process_request(user_input)

    async def _emit_state(self, state: ExecutionState, context: ExecutionContext, details: Optional[Dict[str, Any]] = None):
        """Emits real-time execution state and AI connectivity telemetry to the EventBus and HUD."""
        self.current_state = state
        context.execution_status = state
        context.log_step(state.value, details)

        payload = {
            "request_id": context.request_id,
            "source": context.source.value if hasattr(context.source, "value") else str(context.source),
            "state": state.value,
            "task_category": context.task_category.value if hasattr(context.task_category, "value") else str(context.task_category),
            "selected_skill": context.selected_skill,
            "selected_model": context.selected_model,
            "selected_agents": context.selected_agents,
            "details": details or {},
            "timestamp": time.time()
        }

        if self.event_bus:
            try:
                await self.event_bus.publish("orchestrator_state_change", payload)
            except Exception as e:
                logger.debug(f"EventBus state publish error: {e}")

    async def _emit_ai_status(self, cap: CapabilityState):
        """Broadcasts AI mode (LOCAL/HYBRID/OFFLINE/DEGRADED) and provider info to HUD."""
        if self.event_bus:
            try:
                await self.event_bus.publish("ai_status", cap.to_hud_payload())
            except Exception as e:
                logger.debug(f"EventBus AI status publish error: {e}")

    async def process_request(self, user_input: UserInput) -> RouterExecutionResult:
        """
        Coordinates the complete 8-step intelligence lifecycle:
        1. Context Creation (RECEIVED)
        2. Context & Memory Retrieval (RETRIEVING_CONTEXT)
        3. Task Understanding & Classification (UNDERSTANDING)
        4. Capability & Strategy Selection (PLANNING & ROUTING)
        5. Permission Validation (WAITING_FOR_CONFIRMATION if destructive)
        6. Execution (EXECUTING)
        7. Result Verification (VERIFYING)
        8. Memory Persistence & Delivery (REMEMBERING & RESPONDING -> COMPLETED)
        """
        start_time = time.time()
        cancelled_before_run = self._cancelled

        # ── Step 1: Create Execution Context ──────────────────────────────
        context = ExecutionContext(
            request_id=user_input.request_id,
            source=user_input.channel,
            user_input=user_input.content,
            session_id=user_input.session_id,
            timestamp=user_input.timestamp,
            timeout_seconds=float(self.config.get("execution_timeout", 30.0))
        )
        await self._emit_state(ExecutionState.RECEIVED, context)
        logger.info(f"[ORCHESTRATOR:RECEIVED] [{context.source}] Request {context.request_id[:8]}: '{context.user_input}'")

        if cancelled_before_run:
            self._cancelled = False
            await self._emit_state(ExecutionState.CANCELLED, context)
            return self._build_result(context, "cancelled", "Operation was cancelled before execution.", start_time, ExecutionState.CANCELLED)

        # ── Step 1b: Context Preparation & Reference Resolution ───────────
        try:
            prep_data = self.context_manager.prepare_context(context.user_input, context.session_id)
            context.resolved_input = prep_data.get("resolved_input", context.user_input)
            context.context_messages = prep_data.get("history_window", [])
            
            if prep_data.get("active_task"):
                context.active_task_id = prep_data["active_task"].get("task_id")
                
            if prep_data.get("requires_clarification"):
                await self._emit_state(ExecutionState.COMPLETED, context)
                return self._build_result(context, "ambiguous", "Which item do you mean? Please clarify your reference.", start_time, ExecutionState.COMPLETED)
        except Exception as e:
            logger.warning(f"Context preparation failed (non-fatal): {e}")

        # ── Step 1c: Interaction Pre-Processing (Personality & Strategy) ────
        # Determines emotional signal, interaction state, and response strategy
        # BEFORE the orchestrator executes. This is a pure read-only analysis.
        _interaction_state = None
        _interaction_signal = None
        _interaction_strategy = None

        # Social interaction short-circuit: greetings handled without activating tools
        if self.interaction_engine:
            try:
                social_output = self.interaction_engine.handle_social(
                    user_input.content, session_id=context.session_id
                )
                if social_output:
                    await self._emit_state(ExecutionState.COMPLETED, context)
                    logger.info("[ORCHESTRATOR] Social interaction short-circuit.")
                    return self._build_result(
                        context, "success", social_output.text, start_time, ExecutionState.COMPLETED
                    )
            except Exception as _se:
                logger.debug(f"Social check error (non-fatal): {_se}")

        # Interruption semantic detection
        if self.interaction_engine:
            try:
                stop_voice, stop_task = self.interaction_engine.check_interruption(user_input.content)
                if stop_voice and not stop_task:
                    # "Stop talking" — suppress voice, do NOT cancel task
                    if self.event_bus:
                        await self.event_bus.publish("voice_stop_request", {"reason": "user_interruption"})
                    await self._emit_state(ExecutionState.COMPLETED, context)
                    return self._build_result(
                        context, "success", "", start_time, ExecutionState.COMPLETED
                    )
            except Exception as _inte:
                logger.debug(f"Interruption check error (non-fatal): {_inte}")

        if self.interaction_engine:
            try:
                effective_input = context.resolved_input or context.user_input
                history_texts = [
                    m.get("content", "") for m in (context.context_messages or [])[-5:]
                ]
                _interaction_state, _interaction_signal, _interaction_strategy = \
                    self.interaction_engine.pre_process(
                        user_input=effective_input,
                        session_id=context.session_id,
                        task_category=context.task_category.value if hasattr(context.task_category, "value") else str(context.task_category),
                        channel=user_input.channel.value if hasattr(user_input.channel, "value") else str(user_input.channel),
                        history=history_texts,
                        active_task_id=context.active_task_id,
                    )
                context.interaction_strategy = _interaction_strategy
            except Exception as _ipe:
                logger.debug(f"Interaction pre-process error (non-fatal): {_ipe}")

        # ── Step 2: Context Analysis & Memory Retrieval ───────────────────
        await self._emit_state(ExecutionState.RETRIEVING_CONTEXT, context)
        try:
            # 2a. Route intent (using resolved input if available)
            effective_input = context.resolved_input or context.user_input
            
            # Create a temporary UserInput object for the router to use the resolved text
            resolved_user_input = UserInput(
                content=effective_input,
                channel=user_input.channel,
                session_id=user_input.session_id,
                metadata=user_input.metadata,
                request_id=user_input.request_id,
                timestamp=user_input.timestamp
            )
            context.detected_intent = self.intent_router.route(resolved_user_input)
            # 2b. Classify task
            context.task_category = self.decision_engine.classify_task(effective_input, context.detected_intent)

            # 2c. Retrieve memory context if helpful
            if self.memory and self.decision_engine.requires_memory_context(context.task_category, effective_input):
                try:
                    ctx_snippet = self.memory.retrieve_context(effective_input)
                    if ctx_snippet:
                        context.relevant_memory = [{"type": "retrieval", "content": ctx_snippet}]
                except Exception as mem_err:
                    logger.warning(f"Memory context retrieval failed (non-fatal): {mem_err}")
        except Exception as e:
            logger.error(f"Error in context retrieval: {e}")

        # ── Step 3: Capability Detection & Strategy Selection ─────────────
        await self._emit_state(ExecutionState.PLANNING, context)
        cap = self.capability_detector.detect(
            llm_provider=self.llm_provider,
            memory_manager=self.memory,
            cloud_manager=self.cloud_manager
        )
        await self._emit_ai_status(cap)
        
        # Evaluate skill availability against the detected hardware/cloud state
        self.skill_registry.capability_registry.evaluate_availability(cap)

        skill_name = context.detected_intent.skill_name if context.detected_intent else "conversation"
        context.selected_skill = skill_name

        strategy, _model_placeholder, tools, agents = self.decision_engine.select_strategy_and_capabilities(
            context.task_category, skill_name, context.user_input, self.config
        )

        # ── Step 3b: Hybrid Intelligent Model Routing ─────────────────────
        complexity = classify_complexity(context.user_input, context.task_category)
        privacy_level = detect_privacy_level(
            context.user_input, context.task_category, self.model_router.default_privacy_policy
        )

        # Build cloud provider status from capability detector
        cloud_statuses = cap.cloud_providers or {}

        routing_request = ModelSelectionRequest(
            task_category=context.task_category,
            user_input=context.user_input,
            complexity=complexity,
            privacy_level=privacy_level,
            internet_available=cap.internet_available,
            local_llm_available=cap.local_llm_available,
            cloud_available=cap.cloud_available,
            cloud_providers=cloud_statuses,
            latency_preference="low" if context.source == InputChannel.VOICE else "normal",
            source=context.source.value if hasattr(context.source, "value") else str(context.source),
            skill_name=skill_name,
        )
        logger.info("ROUTING_STARTED")
        routing_result = self.model_router.select(routing_request)

        # Format model identifier
        if routing_result.provider == "none":
            model = None
        elif routing_result.provider == "local":
            model = f"local:{routing_result.model}"
        else:
            model = f"cloud:{routing_result.model}"
            
        logger.info(f"MODEL_SELECTED: {model}")

        context.execution_strategy = strategy
        context.selected_model = model
        context.selected_tools = tools
        context.selected_agents = agents
        context.routing_status = routing_result.routing_status.value
        context.routing_reason = routing_result.reason
        context.privacy_policy = privacy_level.value if hasattr(privacy_level, "value") else str(privacy_level)
        context.needs_verification = self.decision_engine.requires_verification(context.task_category, skill_name)

        # Emit routing telemetry
        routing_hud = self.model_router.to_hud_payload(routing_result)
        await self._emit_state(ExecutionState.ROUTING, context, {
            "strategy": strategy, "model": model, "skill": skill_name, "agents": agents,
            "ai_mode": cap.active_mode.value, "routing": routing_hud
        })

        # ── Step 4: Permission & Confirmation Check ───────────────────────
        action_name = context.detected_intent.action if context.detected_intent else skill_name
        perm_level = self.security.get_permission_level(action_name)
        context.permission_level = perm_level.value if hasattr(perm_level, "value") else str(perm_level)

        if perm_level == PermissionLevel.RESTRICTED:
            context.confirmation_required = True
            await self._emit_state(ExecutionState.WAITING_FOR_CONFIRMATION, context)
            confirmed = self.security.request_confirmation(action_name, context.user_input)
            context.confirmation_granted = confirmed

            if not confirmed:
                logger.info(f"[ORCHESTRATOR:DENIED] Action '{action_name}' rejected by confirmation gate.")
                elapsed = round((time.time() - start_time) * 1000, 2)
                await self._emit_state(ExecutionState.CANCELLED, context)
                return RouterExecutionResult(
                    intent=context.detected_intent.__dict__ if context.detected_intent else {},
                    skill=skill_name,
                    status="permission_denied",
                    response=f"Action '{action_name}' was cancelled: Elevated confirmation was denied.",
                    execution_time_ms=elapsed,
                    request_id=context.request_id,
                    state=ExecutionState.CANCELLED
                )

        # ── Step 5: Execution (with Offline Fallback Handling) ─────────────
        if self._cancelled:
            await self._emit_state(ExecutionState.CANCELLED, context)
            return self._build_result(context, "cancelled", "Operation was cancelled before execution.", start_time, ExecutionState.CANCELLED)

        await self._emit_state(ExecutionState.EXECUTING, context)
        execution_response_text = ""
        execution_status = "success"

        try:
            # 5a. Check for unknown or ambiguous intent
            if context.detected_intent and context.detected_intent.intent_type == IntentType.UNKNOWN and context.detected_intent.skill_name == "unknown":
                execution_status = "unknown"
                clarification = (context.detected_intent.parameters or {}).get("clarification_prompt")
                execution_response_text = clarification or "I did not recognize a valid skill or command for your input."

            # 5b. Check offline requirement for online data
            elif not cap.internet_available and ("search the web" in context.user_input.lower() or "latest news" in context.user_input.lower() or "current weather in" in context.user_input.lower()):
                execution_status = "offline_limited"
                execution_response_text = "Internet connection is currently unavailable (Offline Mode). Cannot perform live web research. Local memory, file operations, system tools, and offline planning remain available."

            # 5c. Autonomous Task Planning & Execution Engine path
            elif strategy in ("planned_execution", "multi_agent") and self.planner and self.execution_engine and self.planner.should_plan(context.user_input, context.task_category):
                logger.info(f"[ORCHESTRATOR] Routing complex goal to Autonomous Task Planner & Execution Engine: '{context.user_input}'")
                plan = self.planner.create_plan(
                    goal=context.user_input,
                    category=context.task_category,
                    offline_mode=not cap.internet_available
                )

                if plan.status.value == "FAILED":
                    execution_status = "error"
                    errs = plan.metadata.get("validation_errors", ["Plan validation failed."])
                    execution_response_text = f"Could not create safe plan: {'; '.join(errs)}"
                else:
                    exec_res = await self.execution_engine.execute_plan(
                        plan=plan,
                        session_id=context.session_id,
                        offline_mode=not cap.internet_available
                    )
                    context.result = exec_res
                    if exec_res.get("status") == "cancelled":
                        execution_status = "cancelled"
                        execution_response_text = exec_res.get("summary", "Task plan execution was cancelled.")
                    elif exec_res.get("status") == "timeout":
                        execution_status = "timeout"
                        execution_response_text = exec_res.get("summary", "Task plan execution timed out.")
                    elif exec_res.get("success"):
                        execution_status = "success"
                        execution_response_text = exec_res.get("summary", "Task plan completed successfully.")
                    else:
                        execution_status = "partial_failure" if exec_res.get("completed_steps", 0) > 0 else "error"
                        execution_response_text = exec_res.get("summary", "Task plan execution encountered errors.")

            # 5d. Multi-agent execution path (via MultiAgentCoordinator or legacy agent_manager)
            elif strategy == "multi_agent":
                logger.info("BRAIN_STARTED")
                if self.coordinator:
                    coord_res = await self.coordinator.execute_workflow(
                        task=context.user_input,
                        agent_ids=agents,
                        category=context.task_category.value if hasattr(context.task_category, "value") else str(context.task_category),
                        session_id=context.session_id,
                        timeout=context.timeout_seconds,
                        offline_mode=not cap.internet_available
                    )
                    context.result = coord_res
                    if coord_res.get("status") == "cancelled":
                        execution_status = "cancelled"
                        execution_response_text = coord_res.get("synthesis", "Operation was cancelled.")
                    elif coord_res.get("status") == "timeout":
                        execution_status = "timeout"
                        execution_response_text = coord_res.get("synthesis", "Multi-agent execution timed out.")
                    elif coord_res.get("success"):
                        execution_status = "success"
                        execution_response_text = coord_res.get("synthesis", "Task completed.")
                    else:
                        execution_status = "partial_failure" if coord_res.get("results") else "error"
                        execution_response_text = coord_res.get("synthesis", "Multi-agent task encountered an error.")
                    logger.info("BRAIN_COMPLETED")
                elif self.agent_manager:
                    agent_res = await asyncio.to_thread(
                        self.agent_manager.run_task,
                        context.user_input,
                        None,
                        context.timeout_seconds
                    )
                    if agent_res.get("status") == "ok":
                        execution_response_text = f"Multi-agent coding task completed successfully ({len(agent_res.get('steps', []))} steps executed)."
                        context.result = agent_res
                    elif agent_res.get("status") == "timeout":
                        execution_status = "timeout"
                        execution_response_text = "Multi-agent task execution timed out."
                    else:
                        execution_status = "error"
                        execution_response_text = agent_res.get("message", "Multi-agent coding task failed.")
                    logger.info("BRAIN_COMPLETED")

            # 5d. Direct Skill execution path via SkillRegistry.execute_intent
            else:
                logger.info("BRAIN_STARTED")
                logger.info("TOOL_STARTED")
                skill_context = {
                    "session_id": context.session_id,
                    "channel": context.source,
                    "permissions": context.permissions,
                    "tools": self.tools,
                    "memory": self.memory
                }

                intent = context.detected_intent
                if not intent:
                    intent = Intent(
                        intent_type=IntentType.CONVERSATION,
                        skill_name="conversation",
                        raw_input=context.user_input
                    )

                skill_res: SkillResult = await asyncio.wait_for(
                    asyncio.to_thread(self.skill_registry.execute_intent, intent, skill_context),
                    timeout=context.timeout_seconds
                )
                if skill_res.success:
                    execution_response_text = skill_res.output_text or skill_res.message or "Task completed."
                    context.data = skill_res.data
                    context.result = skill_res
                else:
                    execution_status = "error"
                    execution_response_text = skill_res.message or "Skill execution reported failure."
                    logger.info("TOOL_ERROR")
                logger.info("TOOL_COMPLETED")
                logger.info("BRAIN_COMPLETED")

        except asyncio.TimeoutError:
            execution_status = "timeout"
            execution_response_text = f"Execution timed out after {context.timeout_seconds}s limit."
            logger.warning(f"[ORCHESTRATOR:TIMEOUT] Task exceeded {context.timeout_seconds}s.")
        except Exception as exec_err:
            execution_status = "error"
            execution_response_text = f"Error during execution: {exec_err}"
            logger.error(f"[ORCHESTRATOR:ERROR] Execution failed: {exec_err}", exc_info=True)
            context.errors.append(JarvisError(
                category=ErrorCategory.UNKNOWN,
                message=str(exec_err),
                action=action_name
            ))

        # ── Step 6: Result Verification ───────────────────────────────────
        await self._emit_state(ExecutionState.VERIFYING, context)
        if context.needs_verification:
            context.verification_passed = (execution_status in ("success", "offline_limited"))

        # ── Step 7: Memory Update ─────────────────────────────────────────
        await self._emit_state(ExecutionState.REMEMBERING, context)
        memory_decision = self.decision_engine.should_save_memory(
            context.task_category, skill_name, execution_status == "success", context.user_input
        )
        context.should_save_memory = memory_decision.should_save
        if context.should_save_memory and self.memory:
            try:
                metadata = {
                    "importance": memory_decision.importance.value,
                    "category": memory_decision.category.value
                }
                if memory_decision.project_id:
                    metadata["project_id"] = memory_decision.project_id
                
                self.memory.add_message("user", context.user_input, metadata)
                if execution_response_text:
                    self.memory.add_message("assistant", execution_response_text, metadata)
                context.memory_updates.append({"type": "dialogue", "status": "persisted", "decision": memory_decision.__dict__})
            except Exception as mem_save_err:
                logger.warning(f"Failed to persist execution to memory: {mem_save_err}")

        # ── Step 8: Responding & Final State ──────────────────────────────
        final_state = ExecutionState.COMPLETED if execution_status in ("success", "offline_limited") else (
            ExecutionState.CANCELLED if execution_status == "cancelled" else ExecutionState.FAILED
        )
        
        # ── Step 9: Post-Execution Context Update ─────────────────────────
        try:
            self.context_manager.update_context(
                session_id=context.session_id,
                user_input=context.user_input,
                execution_status=execution_status,
                response=execution_response_text,
                task_category=context.task_category,
                data=context.data
            )
        except Exception as e:
            logger.warning(f"Context manager update failed (non-fatal): {e}")

        await self._emit_state(ExecutionState.RESPONDING, context)
        await self._emit_state(final_state, context)

        # ── Step 10: Personality Post-Processing & Channel Adaptation ─────
        # Applies response strategy, channel adaptation, and personality polish.
        # Personality is consistent regardless of which model was selected.
        adapted_text = execution_response_text
        adapted_voice = ""
        adapted_hud = ""
        if self.interaction_engine:
            try:
                strategy = context.interaction_strategy
                channel_str = user_input.channel.value if hasattr(user_input.channel, "value") else str(user_input.channel)
                task_cat_str = context.task_category.value if hasattr(context.task_category, "value") else str(context.task_category)
                channel_output = self.interaction_engine.post_process(
                    raw_response=execution_response_text,
                    strategy=strategy,
                    channel=channel_str,
                    execution_status=execution_status,
                    routing_status=context.routing_status,
                    session_id=context.session_id,
                    task_category=task_cat_str,
                )
                context.interaction_channel_output = channel_output
                adapted_text = channel_output.text or execution_response_text
                adapted_voice = channel_output.voice
                adapted_hud = channel_output.hud

                # Publish voice and HUD adapted outputs
                if adapted_voice and self.event_bus:
                    try:
                        await self.event_bus.publish("voice_adapted_response", {
                            "text": adapted_voice,
                            "session_id": context.session_id
                        })
                    except Exception:
                        pass
                if adapted_hud and self.event_bus:
                    try:
                        await self.event_bus.publish("hud_status_update", {
                            "status": adapted_hud,
                            "session_id": context.session_id
                        })
                    except Exception:
                        pass

                # Update task context in interaction state
                if execution_status in ("success", "offline_limited"):
                    self.interaction_engine.clear_task_context(context.session_id)
            except Exception as _ppe:
                logger.debug(f"Interaction post-process error (non-fatal): {_ppe}")
                adapted_text = execution_response_text

        return self._build_result(context, execution_status, adapted_text, start_time, final_state)

    def _build_result(
        self,
        context: ExecutionContext,
        status: str,
        response: str,
        start_time: float,
        final_state: ExecutionState = ExecutionState.COMPLETED
    ) -> RouterExecutionResult:
        """Assembles the final structured RouterExecutionResult."""
        elapsed = round((time.time() - start_time) * 1000, 2)
        context.execution_time_ms = elapsed

        return RouterExecutionResult(
            intent=context.detected_intent.__dict__ if context.detected_intent else {},
            skill=context.selected_skill or "unknown",
            status=status,
            response=response,
            actions=context.actions,
            memory_updates=context.memory_updates,
            data=context.data,
            execution_time_ms=elapsed,
            request_id=context.request_id,
            state=final_state,
            errors=[e.to_dict() for e in context.errors]
        )

    async def process_stream(self, user_input: UserInput) -> AsyncGenerator[Dict[str, Any], None]:
        """Streams real-time execution tokens and state transitions."""
        result = await self.process_request(user_input)
        yield {
            "type": "chat_stream",
            "data": {
                "chunk": result.response,
                "skill": result.skill,
                "status": result.status,
                "state": result.state.value if hasattr(result.state, "value") else str(result.state)
            }
        }
