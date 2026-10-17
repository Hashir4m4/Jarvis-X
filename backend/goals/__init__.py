"""
JARVIS X — Goal Management System
Domain package for hierarchical goal modeling, decomposition, and tracking.
"""

from .models import (
    GoalType,
    GoalStatus,
    GoalTask,
    Goal,
    GoalValidationError,
    validate_hierarchy_acyclic,
    compute_hierarchical_progress
)

from .decomposition import (
    GoalDecompositionEngine,
    ProposedGoalPlan
)

from .engine import (
    GoalManagerEngine
)

__all__ = [
    "GoalType",
    "GoalStatus",
    "GoalTask",
    "Goal",
    "GoalValidationError",
    "validate_hierarchy_acyclic",
    "compute_hierarchical_progress",
    "GoalDecompositionEngine",
    "ProposedGoalPlan",
    "GoalManagerEngine"
]
