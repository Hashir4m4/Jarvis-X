import logging
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from .websocket_manager import WebSocketManager
from backend.core.models import UserInput, InputChannel
from backend.automation.system_controller import SystemController

logger = logging.getLogger("JARVIS.API")

app = FastAPI(title="Jarvis X OS API", version="2.0")

from backend.config import get_config

_central_cfg = get_config()
ALLOWED_ORIGINS = list(_central_cfg.network.cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class CommandPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000, description="Command text")
    channel: Optional[str] = Field("ui", max_length=50)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

ws_manager = WebSocketManager()
system_ctrl = SystemController()

# OS Core and legacy fallbacks
jarvis_core = None  # Injected via main.py
jarvis_brain = None  # Backward compatibility
jarvis_kernel = None  # Backward compatibility


@app.get("/health")
async def health_check():
    """System health, memory, and subsystem status check for the HUD."""
    core_online = jarvis_core is not None
    skills_count = len(jarvis_core.skill_registry.list_skills()) if core_online else 0
    brain_online = (jarvis_core.brain is not None) if core_online else (jarvis_brain is not None)
    memory_online = (jarvis_core.memory is not None) if core_online else (jarvis_brain.memory is not None if jarvis_brain else False)
    
    daily_count = 0
    output_count = 0
    if core_online and jarvis_core.memory and hasattr(jarvis_core.memory, "vault"):
        try:
            daily_count = len(jarvis_core.memory.vault.list_daily_notes())
            output_count = len(jarvis_core.memory.vault.list_reports())
        except Exception:
            pass

    return {
        "status": "online",
        "core": core_online,
        "brain": brain_online,
        "kernel": (jarvis_core.kernel is not None) if core_online else (jarvis_kernel is not None),
        "memory": memory_online,
        "memory_stats": {
            "daily_notes": daily_count,
            "output_reports": output_count
        },
        "skills": skills_count,
        "schedules": len(jarvis_core.kernel.scheduler.get_active_schedules()) if (core_online and jarvis_core.kernel) else 0,
        "provider": getattr(_central_cfg.local_ai, "provider", "Unknown"),
        "model": getattr(_central_cfg.local_ai, "model", "Unknown"),
        "mode": getattr(_central_cfg.environment, "mode", "Unknown"),
        "latency": None
    }


@app.post("/api/command")
async def execute_command(payload: CommandPayload):
    """REST endpoint for executing direct commands through JARVIS Core."""
    message = payload.message.strip()
    try:
        channel = InputChannel(payload.channel.lower())
    except (ValueError, AttributeError):
        channel = InputChannel.UI

    if not message:
        return {"status": "error", "message": "No command provided"}

    if jarvis_core:
        user_input = UserInput(content=message, channel=channel, metadata=payload.metadata or {})
        response = await jarvis_core.process_input(user_input)
        return {
            "status": "ok",
            "text": response.text,
            "skill": response.intent.skill_name if response.intent else "unknown",
            "action": response.intent.action if response.intent else "",
            "execution_time_ms": response.execution_time_ms,
            "data": response.data
        }
    return {"status": "error", "message": "JARVIS Core not initialized"}


@app.on_event("startup")
async def startup_event():
    # Start JARVIS Core / Kernel
    if jarvis_core:
        await jarvis_core.start()

        # Forward all core EventBus telemetry to WebSocket clients
        async def forward_telemetry(event_type, data):
            await ws_manager.broadcast("system_stats", data)

        async def forward_voice_state(event_type, data):
            await ws_manager.broadcast("voice_state", data)

        async def forward_agent_status(event_type, data):
            await ws_manager.broadcast("agent_status", data)

        async def forward_schedule(event_type, data):
            await ws_manager.broadcast("schedule_updated", data)

        async def forward_task_exec(event_type, data):
            await ws_manager.broadcast("scheduled_task_executed", data)

        await jarvis_core.kernel.event_bus.subscribe("telemetry_update", forward_telemetry)
        await jarvis_core.kernel.event_bus.subscribe("voice_state", forward_voice_state)
        await jarvis_core.kernel.event_bus.subscribe("agent_status", forward_agent_status)
        await jarvis_core.kernel.event_bus.subscribe("schedule_updated", forward_schedule)
        await jarvis_core.kernel.event_bus.subscribe("scheduled_task_executed", forward_task_exec)

    elif jarvis_kernel:
        await jarvis_kernel.start()
        async def forward_telemetry(event_type, data):
            await ws_manager.broadcast("system_stats", data)
        await jarvis_kernel.event_bus.subscribe("telemetry_update", forward_telemetry)


@app.on_event("shutdown")
async def shutdown_event():
    if jarvis_core:
        await jarvis_core.stop()
    elif jarvis_kernel:
        await jarvis_kernel.stop()


@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    """Handles real-time streaming chat, commands, push-to-talk, and cancellation."""
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            # 1. Action: Push-To-Talk
            if payload.get("action") == "ptt":
                if jarvis_core and jarvis_core.voice_manager:
                    # Trigger PTT asynchronously
                    asyncio.create_task(asyncio.to_thread(jarvis_core.voice_manager.trigger_push_to_talk))
                    # Note: state is updated by voice_manager itself
                continue

            # 1b. Action: Stop Push-To-Talk
            if payload.get("action") == "stop_ptt":
                if jarvis_core and jarvis_core.voice_manager:
                    if hasattr(jarvis_core.voice_manager, "stop_push_to_talk"):
                        jarvis_core.voice_manager.stop_push_to_talk()
                    else:
                        jarvis_core.voice_manager.cancel()
                continue

            # 2. Action: Cancel current operation / Emergency Stop
            if payload.get("action") == "cancel":
                if jarvis_core:
                    if hasattr(jarvis_core, "cancel"):
                        jarvis_core.cancel()
                    if jarvis_core.voice_manager:
                        jarvis_core.voice_manager.cancel()
                    if jarvis_core.agent_manager:
                        jarvis_core.agent_manager.cancel()
                    if hasattr(jarvis_core, "skill_registry") and jarvis_core.skill_registry:
                        desktop = jarvis_core.skill_registry.get_skill("desktop")
                        if desktop and hasattr(desktop, "emergency_stop"):
                            desktop.emergency_stop()
                await ws_manager.broadcast("operation_cancelled", {"status": "ok"})
                continue

            # 3. Action: Direct Command Message
            message = payload.get("message", "")
            if not message:
                continue

            # Echo user message
            await ws_manager.broadcast("chat_message", {"role": "user", "content": message})

            # Process through unified JARVIS Core
            if jarvis_core:
                try:
                    user_input = UserInput(content=message, channel=InputChannel.UI)
                    async for event in jarvis_core.process_stream(user_input):
                        event_type = event.get("type", "chat_stream")
                        event_data = event.get("data", {})
                        await ws_manager.broadcast(event_type, event_data)
                except Exception as e:
                    logger.error(f"Core stream error: {e}")
                    await ws_manager.broadcast("chat_error", {"message": str(e)})

            elif jarvis_brain:
                response_buffer = ""
                try:
                    for chunk in jarvis_brain.chat_stream(message):
                        response_buffer += chunk
                        await ws_manager.broadcast("chat_stream", {"chunk": chunk})
                    await ws_manager.broadcast("chat_complete", {"role": "assistant", "content": response_buffer})
                except Exception as e:
                    logger.error(f"Brain chat error: {e}")
                    await ws_manager.broadcast("chat_error", {"message": str(e)})
            else:
                await ws_manager.broadcast("chat_error", {"message": "JARVIS Core not initialized"})

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
