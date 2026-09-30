import asyncio
import time
import logging
from typing import Dict, Any, Optional, List

from backend.core.models import UserInput, Intent, IntentType, InputChannel, SkillResult
from .context import ExecutionContext, RouterExecutionResult
from .intent_router import IntentRouter
from .tool_registry import ToolRegistry
from backend.skills.registry import SkillRegistry
from backend.memory.memory_api import MemoryAPI

logger = logging.getLogger("JARVIS.Router")


class CentralRouter:
    """
    The Central JARVIS Operating System Router.
    The heart of JARVIS OS coordinating:
    INPUT -> CONTEXT -> INTENT -> PERMISSIONS -> SKILL -> TOOLS/AGENTS -> MEMORY -> RESPONSE
    """

    def __init__(
        self,
        skill_registry: SkillRegistry,
        intent_router: IntentRouter,
        memory_api: Optional[MemoryAPI] = None,
        tool_registry: Optional[ToolRegistry] = None
    ):
        self.skill_registry = skill_registry
        self.intent_router = intent_router
        self.memory = memory_api
        self.tools = tool_registry or ToolRegistry()

        logger.info("Central JARVIS Router initialized successfully.")

    async def execute(
        self,
        user_input: UserInput,
        execution_context: Optional[ExecutionContext] = None
    ) -> RouterExecutionResult:
        """
        Executes an incoming command end-to-end through the complete 7-stage OS pipeline.
        """
        start_time = time.time()
        logger.info(f"[ROUTER:STAGE 1 - INPUT] Channel: [{user_input.channel.value.upper()}], Request: '{user_input.content}' (ID: {user_input.request_id[:8]})")

        # -------------------------------------------------------------
        # STAGE 2: CONTEXT ASSEMBLY
        # -------------------------------------------------------------
        ctx = execution_context or ExecutionContext(
            session_id=user_input.session_id,
            channel=user_input.channel,
            request_id=user_input.request_id,
            metadata=user_input.metadata
        )

        try:
            if self.memory:
                ctx.context_messages = self.memory.retrieve_context(user_input.content, session_id=ctx.session_id, limit=3)
        except Exception as e:
            logger.warning(f"[ROUTER:CONTEXT_WARNING] Memory context retrieval failed: {e}")

        logger.debug(f"[ROUTER:STAGE 2 - CONTEXT] Context prepared with {len(ctx.context_messages)} past items.")

        # -------------------------------------------------------------
        # STAGE 3: INTENT RESOLUTION
        # -------------------------------------------------------------
        intent = self.intent_router.route(user_input)
        logger.info(f"[ROUTER:STAGE 3 - INTENT] Skill: '{intent.skill_name}', Action: '{intent.action}', Confidence: {intent.confidence}")

        # Check Ambiguity
        if intent.parameters.get("is_ambiguous") or intent.action == "clarify":
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"[ROUTER:AMBIGUOUS] Input was ambiguous: '{user_input.content}'")
            return RouterExecutionResult(
                intent={"type": intent.intent_type.value, "skill": intent.skill_name, "action": intent.action, "confidence": intent.confidence},
                skill=intent.skill_name,
                status="ambiguous",
                response="Your request is ambiguous. Please clarify if you'd like to check system status, view metrics, or create a plan.",
                actions=[],
                memory_updates=[],
                execution_time_ms=elapsed_ms,
                request_id=user_input.request_id
            )

        # Check Unknown
        if intent.intent_type == IntentType.UNKNOWN and intent.skill_name == "unknown":
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"[ROUTER:UNKNOWN] Unrecognized intent for: '{user_input.content}'")
            return RouterExecutionResult(
                intent={"type": intent.intent_type.value, "skill": intent.skill_name, "action": intent.action, "confidence": intent.confidence},
                skill="unknown",
                status="error",
                response="I did not recognize a valid skill or command for your input.",
                actions=[],
                memory_updates=[],
                execution_time_ms=elapsed_ms,
                request_id=user_input.request_id
            )

        # -------------------------------------------------------------
        # STAGE 4: PERMISSION VERIFICATION
        # -------------------------------------------------------------
        meta = self.skill_registry.get_metadata(intent.skill_name)
        if meta and meta.permissions and "*" not in ctx.permissions:
            missing_perms = [p for p in meta.permissions if p not in ctx.permissions]
            if missing_perms:
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                err_msg = f"Permission denied: Missing required permission(s): {', '.join(missing_perms)}"
                logger.error(f"[ROUTER:STAGE 4 - SECURITY] {err_msg}")
                return RouterExecutionResult(
                    intent={"type": intent.intent_type.value, "skill": intent.skill_name, "action": intent.action},
                    skill=intent.skill_name,
                    status="permission_denied",
                    response=err_msg,
                    actions=[],
                    memory_updates=[],
                    execution_time_ms=elapsed_ms,
                    request_id=user_input.request_id
                )

        # -------------------------------------------------------------
        # STAGE 5: SKILL & TOOLS/AGENTS EXECUTION (with Timeout Guard)
        # -------------------------------------------------------------
        logger.info(f"[ROUTER:STAGE 5 - EXECUTION] Dispatching to Skill '{intent.skill_name}' (Timeout: {ctx.timeout_seconds}s)")
        skill_context = {
            "session_id": ctx.session_id,
            "channel": ctx.channel,
            "permissions": ctx.permissions,
            "tools": self.tools,
            "memory": self.memory
        }

        try:
            # Execute skill wrapped in timeout guard
            skill_result: SkillResult = await asyncio.wait_for(
                asyncio.to_thread(self.skill_registry.execute_intent, intent, skill_context),
                timeout=ctx.timeout_seconds
            )
        except asyncio.TimeoutError:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            timeout_msg = f"Execution timed out after {ctx.timeout_seconds} seconds."
            logger.error(f"[ROUTER:STAGE 5 - TIMEOUT] {timeout_msg}")
            return RouterExecutionResult(
                intent={"type": intent.intent_type.value, "skill": intent.skill_name, "action": intent.action},
                skill=intent.skill_name,
                status="timeout",
                response=timeout_msg,
                actions=[intent.action] if intent.action else [],
                memory_updates=[],
                execution_time_ms=elapsed_ms,
                request_id=user_input.request_id
            )
        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(f"[ROUTER:STAGE 5 - EXECUTION_ERROR] Unhandled failure in skill '{intent.skill_name}': {e}", exc_info=True)
            return RouterExecutionResult(
                intent={"type": intent.intent_type.value, "skill": intent.skill_name, "action": intent.action},
                skill=intent.skill_name,
                status="error",
                response=f"Skill execution failed: {str(e)}",
                actions=[intent.action] if intent.action else [],
                memory_updates=[],
                execution_time_ms=elapsed_ms,
                request_id=user_input.request_id
            )

        # Check if skill result indicated business/tool failure
        if not skill_result.success:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.warning(f"[ROUTER:STAGE 5 - SKILL_FAILURE] {intent.skill_name}:{intent.action} returned failure: {skill_result.message}")
            return RouterExecutionResult(
                intent={"type": intent.intent_type.value, "skill": intent.skill_name, "action": intent.action},
                skill=intent.skill_name,
                status="error",
                response=skill_result.output_text or skill_result.message,
                actions=[intent.action] if intent.action else [],
                memory_updates=[],
                data=skill_result.data,
                execution_time_ms=elapsed_ms,
                request_id=user_input.request_id
            )

        # -------------------------------------------------------------
        # STAGE 6: MEMORY RECORDING
        # -------------------------------------------------------------
        memory_updates = []
        if self.memory and skill_result.output_text and intent.skill_name != "conversation":
            try:
                # 1. Update SQLite dialogue log
                msg_id = self.memory.add_message("user", user_input.content)
                asst_id = self.memory.add_message("assistant", skill_result.output_text)
                memory_updates.append({"type": "sqlite_dialogue", "ids": [msg_id, asst_id]})

                # 2. For persistent vault actions, record vault update
                if intent.skill_name == "vault" and intent.action == "set_secret":
                    vault_path = self.memory.vault.create_daily_note(
                        f"Stored memory: {intent.parameters.get('key')} = {intent.parameters.get('value')}"
                    )
                    memory_updates.append({"type": "vault_note", "path": vault_path})

                logger.debug(f"[ROUTER:STAGE 6 - MEMORY] Recorded {len(memory_updates)} memory update(s).")
            except Exception as e:
                logger.error(f"[ROUTER:STAGE 6 - MEMORY_ERROR] Failed to persist memory: {e}", exc_info=True)
                # Note: We do not fail the user's execution if memory fails, but we track the warning
                memory_updates.append({"type": "memory_error", "error": str(e)})

        # -------------------------------------------------------------
        # STAGE 7: STRUCTURED RESPONSE GENERATION
        # -------------------------------------------------------------
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        logger.info(f"[ROUTER:STAGE 7 - RESPONSE] Completed in {elapsed_ms}ms | Status: SUCCESS")

        return RouterExecutionResult(
            intent={
                "type": intent.intent_type.value,
                "skill": intent.skill_name,
                "action": intent.action,
                "parameters": intent.parameters,
                "confidence": intent.confidence
            },
            skill=intent.skill_name,
            status="success",
            response=skill_result.output_text,
            actions=[intent.action] if intent.action else [],
            memory_updates=memory_updates,
            data=skill_result.data,
            execution_time_ms=elapsed_ms,
            request_id=user_input.request_id
        )
