import os
filepath = r'backend\proactive\engine.py'
with open(filepath, 'r', encoding='utf-8') as f:
    code = f.read()

# Add imports for decision engine and scheduler
if 'from .decision import ProactiveDecisionEngine, DecisionAction' not in code:
    code = code.replace('from .storage import ProactiveStorage', 
        'from .storage import ProactiveStorage\nfrom .decision import ProactiveDecisionEngine, DecisionAction\nfrom .scheduler import ProactiveScheduler\nimport asyncio\n')

# Update __init__ to accept memory, planner, executor
if 'self.task_planner = ' not in code:
    code = code.replace('config: Optional[Dict[str, Any]] = None',
        'config: Optional[Dict[str, Any]] = None,\n        memory_system=None,\n        task_planner=None,\n        execution_engine=None')
    code = code.replace('self.config = config or {}',
        'self.config = config or {}\n        self.memory = memory_system\n        self.task_planner = task_planner\n        self.execution_engine = execution_engine\n        self.decision_engine = ProactiveDecisionEngine(task_planner, execution_engine)\n        self.scheduler = ProactiveScheduler(event_bus)')

# Update start and stop to include scheduler
if 'await self.scheduler.start()' not in code:
    code = code.replace('await self.monitors.start()', 'await self.monitors.start()\n        await self.scheduler.start()')
    code = code.replace('await self.monitors.stop()', 'await self.monitors.stop()\n        await self.scheduler.stop()')

# Update handle_event logic
handle_event_patch = '''
                notif = ProactiveNotification(
                    title=rule.name,
                    message=formatted_msg,
                    priority=rule.priority,
                    importance_score=importance_score,
                    suggestion=rule.proactive_suggestion,
                    source_rule_id=rule.rule_id,
                    timestamp=now
                )
                
                # Decision Engine
                decision = self.decision_engine.evaluate(event, rule.proactive_suggestion)
                
                if decision == DecisionAction.EXECUTE and self.task_planner and self.execution_engine:
                    goal = rule.proactive_suggestion or f"Address {rule.name}"
                    from backend.planning.models import TaskCategory
                    plan = self.task_planner.create_plan(goal)
                    if plan:
                        asyncio.create_task(self.execution_engine.execute_plan(plan))
                        notif.message += " [Auto-Executing]"
                        if self.memory:
                            self.memory.add_memory(f"Proactively executing: {goal}")
                elif decision == DecisionAction.ASK_CONFIRMATION:
                    notif.message += " [Requires Confirmation]"
                    event.state = EventState.NOTIFIED
                
                if self.memory and importance_score >= 3:
                    self.memory.add_memory(f"Proactive Alert: {formatted_msg}")

                # Broadcast notification to Queue
'''
code = code.replace('''                notif = ProactiveNotification(
                    title=rule.name,
                    message=formatted_msg,
                    priority=rule.priority,
                    importance_score=importance_score,
                    suggestion=rule.proactive_suggestion,
                    source_rule_id=rule.rule_id,
                    timestamp=now
                )

                # Broadcast notification to Queue''', handle_event_patch)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(code)

print('Patched engine.py successfully')
