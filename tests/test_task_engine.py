import unittest
import asyncio
import json
import time
from unittest.mock import MagicMock, AsyncMock, patch

from backend.planning.models import TaskPlan, TaskStep, PlanStatus, StepStatus, RiskLevel, AutonomyLevel, RetryPolicy
from backend.planning.planner import TaskPlanner
from backend.planning.analyzer import PlanAnalyzer, PlanValidationError
from backend.planning.execution_engine import ExecutionEngine
from backend.core.models import Intent, IntentType

class TestTaskEngine(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.mock_llm = MagicMock()
        
        # Default LLM response for dynamic planning
        self.mock_llm.chat_sync.return_value = json.dumps({
            "steps": [
                {
                    "step_id": "step_1",
                    "description": "Simple action",
                    "action_type": "evaluate",
                    "dependencies": []
                }
            ]
        })

        self.analyzer = PlanAnalyzer()
        self.planner = TaskPlanner(analyzer=self.analyzer, llm_client=self.mock_llm)
        self.planner.llm = self.mock_llm
        
        self.mock_security = MagicMock()
        self.mock_security.request_confirmation.return_value = True
        
        self.engine = ExecutionEngine(
            analyzer=self.analyzer,
            security_proxy=self.mock_security,
            config={"max_execution_time_seconds": 1.0}
        )
        self.engine.planner = self.planner

    async def test_01_simple_task(self):
        plan = self.planner.create_plan("Do a simple thing")
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        self.assertEqual(plan.status, PlanStatus.COMPLETED)

    async def test_02_multi_step_task(self):
        self.mock_llm.chat_sync.return_value = json.dumps({
            "steps": [
                {"step_id": "s1", "description": "Step 1", "action_type": "eval", "dependencies": []},
                {"step_id": "s2", "description": "Step 2", "action_type": "eval", "dependencies": ["s1"]}
            ]
        })
        plan = self.planner.create_plan("Multi step task")
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        self.assertEqual(res["completed_steps"], 2)

    async def test_03_dependency_handling(self):
        self.mock_llm.chat_sync.return_value = json.dumps({
            "steps": [
                {"step_id": "s1", "description": "Step 1", "action_type": "eval", "dependencies": []},
                {"step_id": "s2", "description": "Step 2", "action_type": "eval", "dependencies": ["s1"]},
                {"step_id": "s3", "description": "Step 3", "action_type": "eval", "dependencies": ["s2"]}
            ]
        })
        plan = self.planner.create_plan("Dep task")
        # Validate order
        order = self.analyzer.get_topological_order(plan)
        self.assertEqual(order, ["s1", "s2", "s3"])

    async def test_04_to_06_failure_retry_exhaustion(self):
        plan = self.planner.create_plan("Fail task")
        plan.steps[0].retry_policy = RetryPolicy.LIMITED_RETRY
        plan.steps[0].max_retries = 2
        # Mock dispatch to always fail
        self.engine._dispatch_capability = AsyncMock(side_effect=Exception("Simulated failure"))
        res = await self.engine.execute_plan(plan)
        
        self.assertFalse(res["success"])
        self.assertEqual(plan.steps[0].retry_count, 3) # 1 initial + 2 retries
        self.assertEqual(plan.steps[0].status, StepStatus.FAILED)

    async def test_08_re_planning(self):
        plan = self.planner.create_plan("Replan task")
        self.engine._dispatch_capability = AsyncMock(side_effect=Exception("Simulated failure"))
        
        # Engine should call modify_plan on planner when a step fails
        with patch.object(self.planner, 'modify_plan', wraps=self.planner.modify_plan) as mock_modify:
            await self.engine.execute_plan(plan)
            self.assertTrue(mock_modify.called)
            
    async def test_09_cancellation(self):
        plan = self.planner.create_plan("Long task")
        
        async def slow_dispatch(*args, **kwargs):
            self.engine.cancel(plan.plan_id)
            await asyncio.sleep(0.5)
            return "done"
            
        self.engine._dispatch_capability = slow_dispatch
        res = await self.engine.execute_plan(plan)
        self.assertEqual(plan.status, PlanStatus.CANCELLED)
        
    async def test_10_pause_resume(self):
        plan = self.planner.create_plan("Pause task")
        
        async def background_pause():
            await asyncio.sleep(0.05)
            self.engine.pause(plan.plan_id)
            await asyncio.sleep(0.1)
            self.engine.resume(plan.plan_id)
            
        asyncio.create_task(background_pause())
        res = await self.engine.execute_plan(plan)
        self.assertTrue(res["success"])
        
    async def test_11_12_approval_denied(self):
        plan = self.planner.create_plan("Risk task")
        plan.autonomy_level = AutonomyLevel.MANUAL
        plan.steps[0].risk_level = RiskLevel.HIGH
        
        # Deny
        self.mock_security.request_confirmation.return_value = False
        res = await self.engine.execute_plan(plan)
        self.assertEqual(plan.steps[0].status, StepStatus.FAILED)
        self.assertIn("Permission denied", plan.steps[0].error)

    async def test_13_timeout(self):
        plan = self.planner.create_plan("Timeout task")
        
        async def stall(*args, **kwargs):
            await asyncio.sleep(1.5)
            
        self.engine._dispatch_capability = stall
        res = await self.engine.execute_plan(plan)
        self.assertEqual(res["status"], "timeout")

    async def test_14_loop_detection(self):
        plan = self.planner.create_plan("Loop task")
        plan.steps[0].retry_count = 0
        plan.steps[0].max_retries = 10
        
        # Make the dispatch constantly throw so it triggers replanning, but replanning will just loop
        # Wait, loop detection catches the exact same step hash 3 times
        for i in range(4):
            # simulate engine executing the same step hash
            from backend.planning.execution_engine import hashlib
            h = hashlib.md5(f"{plan.steps[0].action_type}:{plan.steps[0].description}:{str(plan.steps[0].input_data)}".encode()).hexdigest()
            self.engine._execution_history.append(h)
            
        # 5th attempt should trigger loop detection
        res = await self.engine.execute_plan(plan)
        self.assertEqual(plan.steps[0].status, StepStatus.FAILED)
        self.assertIn("Execution loop detected", plan.steps[0].error)

    def test_16_malicious_instruction(self):
        # Malicious step should throw PlanValidationError
        self.mock_llm.chat_sync.return_value = json.dumps({
            "steps": [
                {"step_id": "s1", "description": "rm -rf /", "action_type": "eval", "dependencies": []}
            ]
        })
        plan = self.planner.create_plan("Malicious task")
        self.assertEqual(plan.status, PlanStatus.FAILED)
        self.assertIn("Malicious or prohibited pattern", plan.metadata["validation_errors"][0])

if __name__ == '__main__':
    unittest.main()
