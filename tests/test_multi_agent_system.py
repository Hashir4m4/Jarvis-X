"""
Unit and Integration Tests for the Controlled Multi-Agent Intelligence System in JARVIS.

Covers all 17 required scenarios:
1. Agent registration
2. Agent discovery
3. Simple request without delegation
4. Research Agent selection
5. Coding Agent selection
6. Planning Agent selection
7. Multi-agent workflow
8. Agent unavailable
9. Tool permission restriction
10. Offline agent routing
11. Cloud agent routing
12. Agent timeout
13. Agent cancellation
14. Partial agent failure
15. Delegation depth limit
16. Duplicate agent ID rejection
17. Agent result synthesis
"""

import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.agents.agent_models import (
    AgentStatus,
    AgentCapability,
    OfflineSupport,
    AgentMetadata,
    AgentTaskContext,
    AgentResult
)
from backend.agents.base_agent import BaseAgent
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
from backend.orchestrator.decision_engine import DecisionEngine
from backend.core.models import TaskCategory, UserInput, InputChannel, ExecutionState
from backend.skills.registry import SkillRegistry
from backend.router.intent_router import IntentRouter


class TestMultiAgentIntelligenceSystem(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.registry = AgentRegistry()
        self.research_agent = ResearchAgent()
        self.coding_agent = CodingAgent()
        self.planning_agent = PlanningAgent()
        self.analysis_agent = AnalysisAgent()
        self.system_agent = SystemAgent()
        self.productivity_agent = ProductivityAgent()

        for agent in [
            self.research_agent,
            self.coding_agent,
            self.planning_agent,
            self.analysis_agent,
            self.system_agent,
            self.productivity_agent
        ]:
            self.registry.register(agent)

        self.mock_security = MagicMock()
        self.mock_security.check_permission.return_value = True
        self.mock_security.get_permission_level.return_value = MagicMock(value="read_only")

        self.mock_tools = MagicMock()
        self.mock_event_bus = MagicMock()
        self.mock_event_bus.publish = AsyncMock()

        self.coordinator = MultiAgentCoordinator(
            registry=self.registry,
            event_bus=self.mock_event_bus,
            security=self.mock_security,
            tools=self.mock_tools,
            model_router=None,
            config={"max_depth": 2, "max_agents_per_task": 4, "agent_timeout_seconds": 10.0}
        )

    # 1. Agent registration
    async def test_01_agent_registration(self):
        meta = self.registry.get_metadata("research_agent")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.name, "Research Agent")
        self.assertIn(AgentCapability.WEB_RESEARCH, meta.capabilities)
        self.assertTrue(self.registry.has_agent("coding_agent"))
        self.assertTrue(self.registry.has_agent("planning_agent"))

    # 2. Agent discovery
    async def test_02_agent_discovery(self):
        researchers = self.registry.find_by_capability(AgentCapability.WEB_RESEARCH)
        self.assertEqual(len(researchers), 1)
        self.assertEqual(researchers[0].agent_id, "research_agent")

        coders = self.registry.find_by_capability(AgentCapability.CODE_ANALYSIS)
        self.assertEqual(len(coders), 1)
        self.assertEqual(coders[0].agent_id, "coding_agent")

        all_agents = self.registry.list_agents()
        self.assertEqual(len(all_agents), 6)

    # 3. Simple request without delegation
    async def test_03_simple_request_without_delegation(self):
        engine = DecisionEngine()
        strategy, model, tools, agents = engine.select_strategy_and_capabilities(
            task_cat=TaskCategory.COMMAND,
            skill_name="system",
            user_input="What time is it?",
            config={}
        )
        self.assertNotEqual(strategy, "multi_agent")
        self.assertEqual(agents, [])

        strategy_cpu, _, _, agents_cpu = engine.select_strategy_and_capabilities(
            task_cat=TaskCategory.COMMAND,
            skill_name="system",
            user_input="What is my CPU usage?",
            config={}
        )
        self.assertEqual(strategy_cpu, "direct_skill")
        self.assertEqual(agents_cpu, [])

    # 4. Research Agent selection
    async def test_04_research_agent_selection(self):
        engine = DecisionEngine()
        strategy, model, tools, agents = engine.select_strategy_and_capabilities(
            task_cat=TaskCategory.RESEARCH_TASK,
            skill_name="conversation",
            user_input="Research AI agent frameworks and compare them.",
            config={}
        )
        self.assertEqual(strategy, "multi_agent")
        self.assertIn("research_agent", agents)
        self.assertIn("analysis_agent", agents)

    # 5. Coding Agent selection
    async def test_05_coding_agent_selection(self):
        engine = DecisionEngine()
        strategy, model, tools, agents = engine.select_strategy_and_capabilities(
            task_cat=TaskCategory.CODING_TASK,
            skill_name="coding",
            user_input="Analyze this error in my python code and propose a fix.",
            config={}
        )
        self.assertEqual(strategy, "multi_agent")
        self.assertIn("coding_agent", agents)

    # 6. Planning Agent selection
    async def test_06_planning_agent_selection(self):
        engine = DecisionEngine()
        strategy, model, tools, agents = engine.select_strategy_and_capabilities(
            task_cat=TaskCategory.PLANNING_TASK,
            skill_name="plan",
            user_input="Create a development roadmap for JARVIS OS.",
            config={}
        )
        self.assertEqual(strategy, "multi_agent")
        self.assertIn("planning_agent", agents)

    # 7. Multi-agent workflow
    async def test_07_multi_agent_workflow(self):
        task = "Research three AI frameworks and recommend one for JARVIS."
        result = await self.coordinator.execute_workflow(
            task=task,
            agent_ids=["research_agent", "analysis_agent"],
            category="knowledge_query"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        self.assertIn("research_agent", result["results"])
        self.assertIn("analysis_agent", result["results"])
        self.assertTrue(len(result["synthesis"]) > 0)
        self.assertIn("Research Findings", result["synthesis"])

    # 8. Agent unavailable
    async def test_08_agent_unavailable(self):
        result = await self.coordinator.execute_workflow(
            task="Perform unknown task",
            agent_ids=["non_existent_agent"],
            category="custom"
        )
        self.assertFalse(result["success"])
        self.assertIn("non_existent_agent", result["errors"])
        self.assertIn("not found or inactive", result["errors"]["non_existent_agent"])

    # 9. Tool permission restriction
    async def test_09_tool_permission_restriction(self):
        # Research Agent is not allowed shell_execute, file_delete, or desktop automation
        self.assertFalse(self.research_agent.is_tool_allowed("shell_execute"))
        self.assertFalse(self.research_agent.is_tool_allowed("delete_file"))
        self.assertFalse(self.research_agent.is_tool_allowed("desktop_click"))
        self.assertTrue(self.research_agent.is_tool_allowed("web.search"))
        self.assertTrue(self.research_agent.is_tool_allowed("browser.extract"))

        # Coding Agent is not allowed shell_arbitrary or desktop_click
        self.assertFalse(self.coding_agent.is_tool_allowed("shell_execute"))
        self.assertFalse(self.coding_agent.is_tool_allowed("desktop_click"))
        self.assertTrue(self.coding_agent.is_tool_allowed("file.read"))
        self.assertTrue(self.coding_agent.is_tool_allowed("code.analyze"))

        # Planning Agent is restricted to planning tools only, not system/destructive
        self.assertFalse(self.planning_agent.is_tool_allowed("shell_execute"))
        self.assertFalse(self.planning_agent.is_tool_allowed("delete_file"))
        self.assertTrue(self.planning_agent.is_tool_allowed("plan.decompose"))

    # 10. Offline agent routing
    async def test_10_offline_agent_routing(self):
        context = AgentTaskContext(
            task_id="offline_test_01",
            user_goal="Research today's AI news",
            internet_available=False
        )
        res = await asyncio.to_thread(self.research_agent.execute, context)
        self.assertTrue(res.success)
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        # Should gracefully report offline limitations rather than failing or fabricating
        self.assertIn("unavailable", res.summary.lower())
        self.assertIn("offline_mode", res.artifacts)
        self.assertTrue(res.artifacts["offline_mode"])

    # 11. Cloud agent routing
    async def test_11_cloud_agent_routing(self):
        # Mock model router selecting cloud provider
        mock_router = MagicMock()
        mock_res = MagicMock()
        mock_res.provider = "cloud"
        mock_res.model = "claude-3-5-sonnet"
        mock_router.select.return_value = mock_res
        self.coordinator.model_router = mock_router

        task = "Deep architectural analysis of memory system"
        result = await self.coordinator.execute_workflow(
            task=task,
            agent_ids=["coding_agent"],
            category="coding",
            offline_mode=False
        )
        self.assertTrue(result["success"])
        self.assertIn("coding_agent", result["results"])
        coding_res = result["results"]["coding_agent"]
        self.assertEqual(str(coding_res["status"]).upper(), "COMPLETED")

    # 12. Agent timeout
    async def test_12_agent_timeout(self):
        # Create a slow agent
        class SlowAgent(BaseAgent):
            def __init__(self):
                super().__init__(AgentMetadata(
                    agent_id="slow_agent",
                    name="Slow Agent",
                    description="Simulates hanging execution",
                    specialization="delay",
                    capabilities=[AgentCapability.TECHNICAL_ANALYSIS]
                ))
            def can_handle(self, task_context: AgentTaskContext) -> bool:
                return True
            def execute(self, ctx: AgentTaskContext) -> AgentResult:
                import time as t
                t.sleep(2.0)
                return AgentResult(success=True, agent_id=self.agent_id, task_id=ctx.task_id, status=AgentStatus.COMPLETED)

        self.registry.register(SlowAgent())
        # Set coordinator timeout to 0.1s
        result = await self.coordinator.execute_workflow(
            task="Run slow task",
            agent_ids=["slow_agent"],
            category="testing",
            timeout=0.1
        )
        self.assertEqual(result["status"], "timeout")
        self.assertIn("timed out", result["synthesis"])

    # 13. Agent cancellation
    async def test_13_agent_cancellation(self):
        class CancellableAgent(BaseAgent):
            def __init__(self):
                super().__init__(AgentMetadata(
                    agent_id="cancel_agent",
                    name="Cancel Agent",
                    description="Checks cancellation",
                    specialization="cancel",
                    capabilities=[AgentCapability.TECHNICAL_ANALYSIS]
                ))
            def can_handle(self, task_context: AgentTaskContext) -> bool:
                return True
            def execute(self, ctx: AgentTaskContext) -> AgentResult:
                import time as t
                for _ in range(20):
                    if self._cancelled:
                        return AgentResult(
                            success=False,
                            agent_id=self.agent_id,
                            task_id=ctx.task_id,
                            status=AgentStatus.CANCELLED,
                            summary="Cancelled safely."
                        )
                    t.sleep(0.05)
                return AgentResult(success=True, agent_id=self.agent_id, task_id=ctx.task_id, status=AgentStatus.COMPLETED)

        self.registry.register(CancellableAgent())

        async def cancel_later():
            await asyncio.sleep(0.05)
            self.coordinator.cancel()

        cancel_task = asyncio.create_task(cancel_later())
        result = await self.coordinator.execute_workflow(
            task="Test cancellation pipeline",
            agent_ids=["cancel_agent"],
            category="testing",
            timeout=5.0
        )
        await cancel_task
        self.assertEqual(result["status"], "cancelled")
        self.assertIn("cancelled", result["synthesis"].lower())

    # 14. Partial agent failure
    async def test_14_partial_agent_failure(self):
        class FailingAgent(BaseAgent):
            def __init__(self):
                super().__init__(AgentMetadata(
                    agent_id="failing_agent",
                    name="Failing Agent",
                    description="Fails unconditionally",
                    specialization="error",
                    capabilities=[AgentCapability.TECHNICAL_ANALYSIS]
                ))
            def can_handle(self, task_context: AgentTaskContext) -> bool:
                return True
            def execute(self, ctx: AgentTaskContext) -> AgentResult:
                raise RuntimeError("Simulated crash in sub-agent")

        self.registry.register(FailingAgent())

        result = await self.coordinator.execute_workflow(
            task="Workflow with partial failure",
            agent_ids=["planning_agent", "failing_agent"],
            category="planning"
        )
        # Should NOT crash the entire JARVIS workflow
        self.assertTrue(result["success"])  # Partial success is true when at least one agent succeeded
        self.assertIn("planning_agent", result["results"])
        self.assertIn("failing_agent", result["errors"])
        self.assertIn("Simulated crash", result["errors"]["failing_agent"])
        self.assertIn("Plan Summary", result["synthesis"])

    # 15. Delegation depth limit
    async def test_15_delegation_depth_limit(self):
        result = await self.coordinator.execute_workflow(
            task="Deeply recursive delegation attempt",
            agent_ids=["planning_agent"],
            category="planning",
            delegation_depth=3  # max allowed is 2
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "recursion_limit_exceeded")
        self.assertIn("exceeds safety threshold", result["synthesis"])

    # 16. Duplicate agent ID rejection
    async def test_16_duplicate_agent_id_rejection(self):
        dup_agent = ResearchAgent()
        with self.assertRaises(ValueError):
            self.registry.register(dup_agent)

    # 17. Agent result synthesis
    async def test_17_agent_result_synthesis(self):
        result = await self.coordinator.execute_workflow(
            task="Synthesize research and plan",
            agent_ids=["research_agent", "planning_agent"],
            category="knowledge_query"
        )
        self.assertTrue(result["success"])
        synthesis = result["synthesis"]
        self.assertIn("Research Findings", synthesis)
        self.assertIn("Plan Summary", synthesis)
        # Verify no raw hidden prompts/tokens exposed
        self.assertNotIn("PRIVATE_API_KEY", synthesis)
        self.assertNotIn("system_prompt_secret", synthesis)


if __name__ == "__main__":
    unittest.main()
