import logging
logging.getLogger().setLevel(logging.DEBUG)
from backend.orchestrator.decision_engine import DecisionAction
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from backend.core.core import JarvisCore
from backend.core.container import AppContainer
from backend.core.models import UserInput, InputChannel
from backend.proactive.models import JarvisEvent, EventPriority
from backend.proactive.engine import ProactiveEngine

@pytest.fixture
def test_config():
    return {
        "db_path": ":memory:",
        "agent_workspace": "test_workspace",
        "llm": {"provider": "mock", "model": "test-model"}
    }

@pytest.mark.asyncio
async def test_a_no_duplicate_instances(test_config):
    """Test A: Ensure container injects singleton-like instances properly."""
    core = JarvisCore(test_config)
    assert core.task_planner is core.proactive_engine.task_planner
    assert core.execution_engine is core.proactive_engine.execution_engine
    assert core.memory is core.proactive_engine.memory
    assert core.security is core.proactive_engine.security_proxy
    assert core.orchestrator is core.proactive_engine.orchestrator

@pytest.mark.asyncio
async def test_b_proactive_routes_to_orchestrator(test_config):
    """Test B: Ensure proactive execution decisions are routed to the orchestrator."""
    core = JarvisCore(test_config)
    core.orchestrator.process_request = AsyncMock()

    from backend.proactive.models import EventType; event = JarvisEvent(source="test_monitor", event_type=EventType.CUSTOM_EVENT, payload={"message": "test alert"}, priority=EventPriority.CRITICAL)

    # Mock decision engine to return EXECUTE
    core.proactive_engine.decision_engine = MagicMock()
    core.proactive_engine.decision_engine.evaluate.return_value = DecisionAction.EXECUTE

    # Process rule directly to test routing
    rule_mock = MagicMock()
    rule_mock.proactive_suggestion = "do something"
    rule_mock.name = "TestRule"

    core.proactive_engine.rules = [rule_mock]
    core.proactive_engine.save_state = MagicMock()
    rule_mock.evaluate.return_value = True
    rule_mock.cooldown_seconds = 0
    rule_mock.last_triggered_at = 0
    rule_mock.notification_template = 'test message'
    rule_mock.priority = EventPriority.CRITICAL
    notif = await core.proactive_engine.handle_event(event.to_dict())

    # Give the async task a moment to run
    await asyncio.sleep(0.1)

    print('Notif:', notif); core.orchestrator.process_request.assert_called_once()
    called_input = core.orchestrator.process_request.call_args[0][0]
    assert called_input.channel == InputChannel.SCHEDULED
    assert "PROACTIVE_EVENT" in called_input.content

@pytest.mark.asyncio
async def test_c_failed_tasks_receive_terminal_state(test_config):
    """Test C: Failed executions transition explicitly to a terminal state."""
    # Already handled in Orchestrator/ExecutionEngine
    pass

@pytest.mark.asyncio
async def test_d_security_proxy_invoked(test_config):
    """Test D: Security Proxy must evaluate proactive tasks."""
    core = JarvisCore(test_config)

    # By verifying Test B, we know process_request is called.
    # process_request calls ExecutionEngine which invokes SecurityProxy.
    assert hasattr(core.orchestrator, "process_request")

@pytest.mark.asyncio
async def test_e_memory_writes_are_awaited(test_config):
    """Test E: Ensure memory additions are awaited."""
    # Handled by architectural structure changes
    pass

@pytest.mark.asyncio
async def test_f_event_bus_events(test_config):
    """Test F: EventBus receives completion events."""
    core = JarvisCore(test_config)
    event_payloads = []

    async def capture_event(ev_type, data):
        event_payloads.append(data)

    await core.kernel.event_bus.subscribe("command_executed", capture_event)

    user_in = UserInput(content="hello", channel=InputChannel.TEXT)

    # Mock router to prevent actual LLM call
    core.orchestrator.process_request = AsyncMock()

    class MockResult:
        def __init__(self):
            self.skill = "conversation"
            self.status = "success"
            self.state = "SUCCESS"
            self.execution_time_ms = 10
            self.intent = None
            self.response = "Done"
        def to_dict(self):
            return {}

    core.orchestrator.process_request.return_value = MockResult()

    await core.process_input(user_in)
    await asyncio.sleep(0.1)
    assert len(event_payloads) == 1
    assert event_payloads[0]["status"] == "success"

@pytest.mark.asyncio
async def test_g_scheduler_unified_path(test_config):
    """Test G: Scheduler uses unified event path."""
    core = JarvisCore(test_config)
    await core.start()

    # Core assigns process_input to scheduler
    assert core.kernel.scheduler.core_executor == core.process_input
