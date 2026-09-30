import logging
from typing import Dict, Any, Optional
from backend.proactive.models import JarvisEvent, EventPriority, ProactiveNotification, EventState

logger = logging.getLogger(__name__)

class DecisionAction(str):
    IGNORE = "IGNORE"
    NOTIFY = "NOTIFY"
    ASK_CONFIRMATION = "ASK_CONFIRMATION"
    EXECUTE = "EXECUTE"

class ProactiveDecisionEngine:
    def __init__(self, task_planner=None, execution_engine=None):
        self.task_planner = task_planner
        self.execution_engine = execution_engine
        
    def evaluate(self, event: JarvisEvent, rule_suggestion: Optional[str] = None) -> str:
        suggestion = str(rule_suggestion).lower()
        if "diagnose" in suggestion or "cleanup" in suggestion or "scan" in suggestion:
            if event.priority in (EventPriority.HIGH, EventPriority.CRITICAL):
                return DecisionAction.ASK_CONFIRMATION
            return DecisionAction.EXECUTE
            
        return DecisionAction.NOTIFY
