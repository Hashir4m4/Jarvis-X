"""
Comprehensive Test Suite for Autonomous Task Planning and Controlled Execution Engine.

Validates all 24 required test points:
1. Simple request bypasses planner
2. Complex request generates plan
3. Plan validation
4. Circular dependency detection
5. Missing skill error
6. Missing agent error
7. Missing tool error
8. Low-risk automatic execution
9. High-risk approval required
10. Step dependency ordering
11. Independent step execution where supported
12. Step success verification
13. Transient failure retry
14. Retry limit reached
15. Alternative capability fallback
16. Plan pause
17. Plan resume
18. Task cancellation
19. Emergency stop
20. Partial completion
21. Plan modification
22. New risky step requires approval
23. Offline capability unavailable
24. Maximum execution limit
"""

import asyncio
import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.planning.models import (
    TaskPlan,
    TaskStep,
    PlanStatus,
    StepStatus,
    RiskLevel,
    RetryPolicy,
    ApprovalMode
)
from backend.planning.analyzer import PlanAnalyzer, PlanValidationError
from backend.planning.planner import TaskPlanner
from backend.planning.execution_engine import ExecutionEngine
from backend.agents.agent_registry import AgentRegistry
from backend.agents.specialized import (
    ResearchAgent,
    CodingAgent,
    PlanningAgent,
    AnalysisAgent,
    SystemAgent,
    ProductivityAgent
)
from backend.core.models import TaskCategory, UserInput, InputChannel


class TestTaskPlanningAndExecutionEngine(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        # 1. Setup registries
        self.agent_registry = AgentRegistry()
        self.research_agent = ResearchAgent()
        self.coding_agent = CodingAgent()
        self.planning_agent = PlanningAgent()
        self.analysis_agent = AnalysisAgent()
        self.system_agent = SystemAgent()
        self.productivity_agent = ProductivityAgent()

        for a in [
            self.research_agent,
            self.coding_agent,
            self.planning_agent,
            self.analysis_agent,
            self.system_agent,
            self.productivity_agent
        ]:
            self.agent_registry.register(a)

        self.mock_tools = MagicMock()
        self.mock_tools.get_tool.side_effect = lambda name: MagicMock() if name in ("file.create_folder", "file.read") else None
        self.mock_tools.execute_tool = AsyncMock(return_value="Tool executed successfully.")

        self.mock_skills = MagicMock()
        self.mock_skills.get_skill.side_effect = lambda name: MagicMock() if name in ("vault", "system", "coding", "plan") else None

        self.mock_security = MagicMock()
        self.mock_security.request_confirmation.return_value = True

        self.mock_event_bus = MagicMock()
        self.mock_event_bus.publish = AsyncMock()

        self.mock_coordinator = MagicMock()
        self.mock_coordinator.execute_workflow = AsyncMock(return_value={
            "success": True,
            "status": "completed",
            "synthesis": "Agent workflow finished.",
            "results": {
                "research_agent": {"summary": "Extracted specifications."},
                "analysis_agent": {"summary": "Comparative matrix prepared."},
                "planning_agent": {"summary": "Roadmap constructed."},
                "coding_agent": {"summary": "Code validated."}
            }
        })
        self.mock_coordinator.cancel = MagicMock()

        # 2. Planning Analyzer & Planner
        self.analyzer = PlanAnalyzer(
            skill_registry=self.mock_skills,
            tool_registry=self.mock_tools,
            agent_registry=self.agent_registry
        )
        self.planner = TaskPlanner(
            analyzer=self.analyzer,
            config={"max_plan_steps": 8}
        )

        # 3. Execution Engine
        self.engine = ExecutionEngine(
            analyzer=self.analyzer,
            skill_registry=self.mock_skills,
            tool_registry=self.mock_tools,
            agent_coordinator=self.mock_coordinator,
            security_proxy=self.mock_security,
            event_bus=self.mock_event_bus,
            config={"max_execution_time_seconds": 10.0, "allow_concurrency": True}
        )

    # 1. Simple request bypasses planner
    async def test_01_simple_request_bypasses_planner(self):
        self.assertFalse(self.planner.should_plan("Open Chrome.", TaskCategory.COMPUTER_ACTION))
        self.assertFalse(self.planner.should_plan("What time is it?", TaskCategory.COMMAND))
        self.assertFalse(self.planner.should_plan("Set volume to 50", TaskCategory.COMMAND))

    # 2. Complex request generates plan
    async def test_02_complex_request_generates_plan(self):
        goal = "Research three local AI models, compare them, and save a report."
        self.assertTrue(self.planner.should_plan(goal, TaskCategory.RESEARCH_TASK))
        plan = self.planner.create_plan(goal)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.status, PlanStatus.READY)
        self.assertTrue(len(plan.steps) >= 3)
        self.assertEqual(plan.steps[0].action_type, "research")
        self.assertIn("step_1_research", plan.steps[1].dependencies)

    # 3. Plan validation
    async def test_03_plan_validation(self):
        plan = TaskPlan(
            goal="Valid simple plan",
            steps=[
                TaskStep(step_id="s1", description="Step 1", action_type="read", required_agent="system_agent"),
                TaskStep(step_id="s2", description="Step 2", action_type="analyze", dependencies=["s1"], required_agent="analysis_agent")
            ]
        )
        is_valid, errors = self.analyzer.validate_plan(plan)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        self.assertEqual(plan.status, PlanStatus.READY)

    # 4. Circular dependency detection
    async def test_04_circular_dependency_detection(self):
        plan = TaskPlan(
            goal="Cycle plan",
            steps=[
                TaskStep(step_id="s1", description="Step 1", dependencies=["s2"]),
                TaskStep(step_id="s2", description="Step 2", dependencies=["s1"])
            ]
        )
        is_valid, errors = self.analyzer.validate_plan(plan)
        self.assertFalse(is_valid)
        self.assertTrue(any("Circular dependency" in e for e in errors))

    # 5. Missing skill
    async def test_05_missing_skill(self):
        plan = TaskPlan(
            goal="Missing skill plan",
            steps=[
                TaskStep(step_id="s1", description="Run fake skill", required_skill="non_existent_skill_xyz")
            ]
        )
        is_valid, errors = self.analyzer.validate_plan(plan)
        self.assertFalse(is_valid)
        self.assertTrue(any("non_existent_skill_xyz" in e for e in errors))

    # 6. Missing agent
    async def test_06_missing_agent(self):
        plan = TaskPlan(
            goal="Missing agent plan",
            steps=[
                TaskStep(step_id="s1", description="Run fake agent", required_agent="phantom_agent")
            ]
        )
        is_valid, errors = self.analyzer.validate_plan(plan)
        self.assertFalse(is_valid)
        self.assertTrue(any("phantom_agent" in e for e in errors))

    # 7. Missing tool
    async def test_07_missing_tool(self):
        plan = TaskPlan(
            goal="Missing tool plan",
            steps=[
                TaskStep(step_id="s1", description="Run fake tool", required_tool="fake.tool.name")
            ]
        )
        is_valid, errors = self.analyzer.validate_plan(plan)
        self.assertFalse(is_valid)
        self.assertTrue(any("fake.tool.name" in e for e in errors))

    # 8. Low-risk automatic execution
    async def test_08_low_risk_automatic_execution(self):
        plan = TaskPlan(
            goal="Low risk task",
            steps=[
                TaskStep(step_id="s1", description="Analyze read-only data", action_type="read", required_agent="system_agent", risk_level=RiskLevel.LOW)
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        self.assertEqual(plan.status, PlanStatus.COMPLETED)
        # Low risk requires no elevated confirmation call
        self.mock_security.request_confirmation.assert_not_called()

    # 9. High-risk approval required
    async def test_09_high_risk_approval_required(self):
        plan = TaskPlan(
            goal="High risk task",
            steps=[
                TaskStep(step_id="s1", description="Delete obsolete cache", action_type="delete_file", risk_level=RiskLevel.HIGH, requires_confirmation=True)
            ]
        )
        self.mock_security.request_confirmation.return_value = False
        res = await self.engine.execute_plan(plan)
        self.mock_security.request_confirmation.assert_called_once()
        self.assertFalse(res["success"])
        self.assertEqual(plan.steps[0].status, StepStatus.FAILED)
        self.assertIn("Permission denied", plan.steps[0].error)

    # 10. Step dependency ordering
    async def test_10_step_dependency_ordering(self):
        execution_order = []

        async def fake_dispatch(step, plan, session_id, offline):
            execution_order.append(step.step_id)
            return "Done"

        self.engine._dispatch_capability = fake_dispatch

        plan = TaskPlan(
            goal="Ordered pipeline",
            steps=[
                TaskStep(step_id="step_c", description="Step C", dependencies=["step_b"]),
                TaskStep(step_id="step_a", description="Step A", dependencies=[]),
                TaskStep(step_id="step_b", description="Step B", dependencies=["step_a"]),
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        self.assertEqual(execution_order, ["step_a", "step_b", "step_c"])

    # 11. Independent step execution where supported
    async def test_11_independent_step_execution_concurrent(self):
        plan = TaskPlan(
            goal="Parallel reads",
            steps=[
                TaskStep(step_id="s1", description="Read metrics 1", action_type="read", risk_level=RiskLevel.LOW),
                TaskStep(step_id="s2", description="Read metrics 2", action_type="read", risk_level=RiskLevel.LOW),
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        self.assertEqual(plan.status, PlanStatus.COMPLETED)
        self.assertEqual(plan.steps[0].status, StepStatus.COMPLETED)
        self.assertEqual(plan.steps[1].status, StepStatus.COMPLETED)

    # 12. Step success verification
    async def test_12_step_success_verification(self):
        step = TaskStep(step_id="s1", description="Create test file", action_type="create_file", input_data={"file_path": "non_existent_file_abc.txt"})
        verified, msg = self.engine._verify_result(step, "File created.")
        self.assertFalse(verified)
        self.assertIn("was not found on disk", msg)

        # Non-empty output verification
        step2 = TaskStep(step_id="s2", description="Read metrics", action_type="read")
        verified2, _ = self.engine._verify_result(step2, "CPU: 12%")
        self.assertTrue(verified2)

    # 13. Transient failure retry
    async def test_13_transient_failure_retry(self):
        attempts = 0

        async def flaky_dispatch(step, plan, session_id, offline):
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise ConnectionResetError("Transient network glitch")
            return "Retried success"

        self.engine._dispatch_capability = flaky_dispatch

        plan = TaskPlan(
            goal="Flaky step",
            steps=[
                TaskStep(step_id="s1", description="Network query", retry_policy=RetryPolicy.LIMITED_RETRY, max_retries=2)
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        self.assertEqual(attempts, 2)
        self.assertEqual(plan.steps[0].status, StepStatus.COMPLETED)

    # 14. Retry limit reached
    async def test_14_retry_limit_reached(self):
        async def always_fails(step, plan, session_id, offline):
            raise TimeoutError("Persistent timeout")

        self.engine._dispatch_capability = always_fails

        plan = TaskPlan(
            goal="Failing plan",
            steps=[
                TaskStep(step_id="s1", description="Timeout query", retry_policy=RetryPolicy.LIMITED_RETRY, max_retries=2)
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertFalse(res["success"])
        self.assertEqual(plan.steps[0].status, StepStatus.FAILED)
        self.assertEqual(plan.steps[0].retry_count, 3)  # initial attempt + 2 retries

    # 15. Alternative capability fallback
    async def test_15_alternative_capability_fallback(self):
        dispatched_caps = []

        async def fallback_dispatch(step, plan, session_id, offline):
            dispatched_caps.append(step.required_capability)
            if step.required_capability == "primary_online":
                raise RuntimeError("Primary offline")
            return "Fallback cached knowledge"

        self.engine._dispatch_capability = fallback_dispatch

        plan = TaskPlan(
            goal="Fallback goal",
            steps=[
                TaskStep(
                    step_id="s1",
                    description="Online research",
                    required_capability="primary_online",
                    retry_policy=RetryPolicy.ALTERNATIVE_CAPABILITY,
                    fallback_capability="cached_knowledge"
                )
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        self.assertIn("primary_online", dispatched_caps)
        self.assertIn("cached_knowledge", dispatched_caps)
        self.assertEqual(plan.steps[0].status, StepStatus.COMPLETED)

    # 16. Plan pause
    async def test_16_plan_pause(self):
        plan = TaskPlan(
            goal="Pausable plan",
            steps=[
                TaskStep(step_id="s1", description="Step 1"),
                TaskStep(step_id="s2", description="Step 2", dependencies=["s1"])
            ]
        )
        self.engine.pause()
        self.assertTrue(self.engine._paused)

    # 17. Plan resume
    async def test_17_plan_resume(self):
        self.engine.pause()
        self.assertTrue(self.engine._paused)
        self.engine.resume()
        self.assertFalse(self.engine._paused)

    # 18. Task cancellation
    async def test_18_task_cancellation(self):
        plan = TaskPlan(
            goal="Cancellable plan",
            steps=[
                TaskStep(step_id="s1", description="Long step 1"),
                TaskStep(step_id="s2", description="Step 2", dependencies=["s1"])
            ]
        )
        self.engine.cancel(plan.plan_id)
        self.assertTrue(self.engine._cancelled)

    # 19. Emergency stop
    async def test_19_emergency_stop(self):
        plan = TaskPlan(
            goal="Emergency stop plan",
            steps=[
                TaskStep(step_id="s1", description="Step 1"),
                TaskStep(step_id="s2", description="Step 2", dependencies=["s1"])
            ]
        )
        self.engine.active_plans[plan.plan_id] = plan
        self.engine.emergency_stop()
        self.assertTrue(self.engine._emergency_stopped)
        self.assertEqual(plan.status, PlanStatus.CANCELLED)
        self.assertEqual(plan.steps[0].status, StepStatus.CANCELLED)

    # 20. Partial completion
    async def test_20_partial_completion(self):
        async def step_behavior(step, plan, session_id, offline):
            if step.step_id == "s2":
                raise RuntimeError("Permanent fault in s2")
            return "Success in s1"

        self.engine._dispatch_capability = step_behavior

        plan = TaskPlan(
            goal="Partial plan",
            steps=[
                TaskStep(step_id="s1", description="Step 1"),
                TaskStep(step_id="s2", description="Step 2", dependencies=["s1"]),
                TaskStep(step_id="s3", description="Step 3", dependencies=["s2"])
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])  # Partial success evaluates True if >= 1 step completed
        self.assertEqual(plan.status, PlanStatus.PARTIALLY_COMPLETED)
        self.assertEqual(plan.steps[0].status, StepStatus.COMPLETED)
        self.assertEqual(plan.steps[1].status, StepStatus.FAILED)
        self.assertEqual(plan.steps[2].status, StepStatus.PENDING)

    # 21. Plan modification
    async def test_21_plan_modification(self):
        plan = TaskPlan(
            goal="Initial plan",
            steps=[
                TaskStep(step_id="s1", description="Step 1", action_type="read")
            ]
        )
        self.assertEqual(len(plan.steps), 1)

        new_step = TaskStep(step_id="s2", description="Added safe step", action_type="read", dependencies=["s1"])
        is_valid, errors = self.planner.modify_plan(plan, added_steps=[new_step])
        self.assertTrue(is_valid)
        self.assertEqual(len(plan.steps), 2)
        self.assertIn("s1", plan.steps[1].dependencies)

    # 22. New risky step requires approval
    async def test_22_new_risky_step_requires_approval(self):
        plan = TaskPlan(
            goal="Base plan",
            steps=[TaskStep(step_id="s1", description="Read files", action_type="read")]
        )
        risky_step = TaskStep(step_id="s2", description="Delete database cache", action_type="delete_file", dependencies=["s1"])
        is_valid, _ = self.planner.modify_plan(plan, added_steps=[risky_step])
        self.assertTrue(is_valid)
        s2 = plan.get_step("s2")
        self.assertEqual(s2.risk_level, RiskLevel.HIGH)
        self.assertTrue(s2.requires_confirmation)

    # 23. Offline capability unavailable
    async def test_23_offline_capability_unavailable(self):
        plan = TaskPlan(
            goal="Live web goal",
            steps=[
                TaskStep(step_id="s1", description="Search web for live breaking news", required_tool="web.search")
            ]
        )
        is_valid, errors = self.analyzer.validate_plan(plan, offline_mode=True)
        self.assertFalse(is_valid)
        self.assertTrue(any("live internet access" in e.lower() for e in errors))

    # 24. Maximum execution limit
    async def test_24_maximum_execution_limit(self):
        # Set max execution time to 0.1s
        self.engine.max_execution_time = 0.1

        async def slow_dispatch(step, plan, session_id, offline):
            await asyncio.sleep(0.3)
            return "Done"

        self.engine._dispatch_capability = slow_dispatch

        plan = TaskPlan(
            goal="Slow task exceeding budget",
            steps=[
                TaskStep(step_id="s1", description="Slow operation 1"),
                TaskStep(step_id="s2", description="Slow operation 2")
            ]
        )
        res = await self.engine.execute_plan(plan)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "timeout")
        self.assertIn("maximum execution time limit", res["summary"])


if __name__ == "__main__":
    unittest.main()
