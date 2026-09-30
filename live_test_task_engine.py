import asyncio
import logging

from backend.planning.models import TaskPlan, TaskStep, RiskLevel
from backend.planning.planner import TaskPlanner
from backend.planning.analyzer import PlanAnalyzer
from backend.planning.execution_engine import ExecutionEngine
from backend.agents.agent_registry import AgentRegistry
from backend.agents.specialized import SystemAgent, ResearchAgent, PlanningAgent

logging.basicConfig(level=logging.WARNING)

async def main():
    print("========================================")
    print(" JARVIS X - AUTONOMOUS TASK ENGINE TEST")
    print("========================================")

    print("\n1. Initializing Task Engine Components...")
    registry = AgentRegistry()
    registry.register(SystemAgent())
    registry.register(ResearchAgent())
    registry.register(PlanningAgent())
    
    analyzer = PlanAnalyzer(agent_registry=registry)
    planner = TaskPlanner(analyzer=analyzer)
    
    # Mock coordinator for demonstration
    class MockCoordinator:
        async def execute_workflow(self, *args, **kwargs):
            return {
                "success": True,
                "status": "completed",
                "synthesis": "Agent workflow finished.",
                "results": {"system_agent": {"summary": "Completed successfully."}}
            }
        def cancel(self):
            pass

    # Mock security proxy
    class MockSecurity:
        def request_confirmation(self, *args, **kwargs):
            print("   [SECURITY] Permission requested for high-risk task... GRANTED (Mocked)")
            return True

    engine = ExecutionEngine(
        analyzer=analyzer,
        agent_coordinator=MockCoordinator(),
        security_proxy=MockSecurity(),
        config={"max_execution_time_seconds": 15.0}
    )
    
    print("\n2. Creating complex task plan (Offline Fallback)...")
    goal = "Research AI trends and generate a roadmap"
    plan = planner.create_plan(goal, offline_mode=True)
    
    print(f"   Task ID: {plan.plan_id}")
    print(f"   Goal: {plan.goal}")
    print(f"   Status: {plan.status.name}")
    print("   Steps Generated:")
    for step in plan.steps:
        print(f"     - [{step.step_id}] {step.description} (Agent: {step.required_agent}, Deps: {step.dependencies})")
        
    print("\n3. Validating plan dependencies...")
    order = analyzer.get_topological_order(plan)
    print(f"   Topological Execution Order: {order}")
    
    print("\n4. Marking a step as HIGH risk to trigger Security Proxy...")
    plan.steps[1].risk_level = RiskLevel.HIGH
    
    print("\n5. Executing Task Plan...")
    # Overwrite the default plan status to READY in case offline_mode validation failed for another reason
    plan.status = 3 # Enum val for READY might be different, let's use the object
    from backend.planning.models import PlanStatus
    plan.status = PlanStatus.READY
    result = await engine.execute_plan(plan)
    
    print("\n========================================")
    print(" EXECUTION RESULTS")
    print("========================================")
    print(f"   Success: {result['success']}")
    print(f"   Status: {result['status']}")
    print(f"   Steps Completed: {result['completed_steps']}/{result['total_steps']}")
    print(f"   Execution Time: {result['execution_time']}s")
    print("\n   Step Statuses:")
    for step in plan.steps:
        print(f"     - {step.step_id}: {step.status.name}")
        
    print("\nLIVE DEMONSTRATION COMPLETE.")

if __name__ == '__main__':
    asyncio.run(main())
