"""
JARVIS X — Goal Management System Models
Data models, validation rules, status transitions, and progress semantics for goals.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Union
import datetime
import time
import uuid
import re


class GoalValidationError(ValueError):
    """Raised when goal validation constraints are violated."""
    pass


class GoalType(str, Enum):
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    LONG_TERM = "LONG_TERM"


class GoalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# Allowed status transitions
ALLOWED_STATUS_TRANSITIONS: Dict[GoalStatus, Set[GoalStatus]] = {
    GoalStatus.PROPOSED: {GoalStatus.ACTIVE, GoalStatus.CANCELLED},
    GoalStatus.ACTIVE: {GoalStatus.PAUSED, GoalStatus.COMPLETED, GoalStatus.CANCELLED},
    GoalStatus.PAUSED: {GoalStatus.ACTIVE, GoalStatus.CANCELLED},
    GoalStatus.COMPLETED: {GoalStatus.ACTIVE},  # Re-opening completed goal is allowed
    GoalStatus.CANCELLED: {GoalStatus.PROPOSED, GoalStatus.ACTIVE},  # Cannot transition directly to COMPLETED
}


@dataclass
class GoalTask:
    """Actionable atomic task assigned to a goal or subgoal."""
    task_id: str = field(default_factory=lambda: f"gtask_{uuid.uuid4().hex[:8]}")
    description: str = ""
    completed: bool = False
    assigned_skill: Optional[str] = None
    target_step: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def __post_init__(self):
        self.validate()

    def validate(self):
        if not self.task_id or not isinstance(self.task_id, str) or not self.task_id.strip():
            raise GoalValidationError("Task task_id must be a non-empty string.")
        if not self.description or not isinstance(self.description, str) or not self.description.strip():
            raise GoalValidationError("Task description must be a non-empty string.")
        if not isinstance(self.completed, bool):
            raise GoalValidationError("Task completed state must be a boolean.")
        if self.completed and self.completed_at is None:
            self.completed_at = time.time()
        elif not self.completed:
            self.completed_at = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "completed": self.completed,
            "assigned_skill": self.assigned_skill,
            "target_step": self.target_step,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalTask":
        if not isinstance(data, dict):
            raise GoalValidationError("GoalTask.from_dict requires a dictionary.")
        return cls(
            task_id=data.get("task_id") or f"gtask_{uuid.uuid4().hex[:8]}",
            description=data.get("description", ""),
            completed=bool(data.get("completed", False)),
            assigned_skill=data.get("assigned_skill"),
            target_step=data.get("target_step"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            completed_at=data.get("completed_at"),
        )


@dataclass
class Goal:
    """
    Core structured Goal definition.
    Supports short-term, medium-term, and long-term goal hierarchies.
    """
    goal_id: str = field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    goal_type: GoalType = GoalType.SHORT_TERM
    status: GoalStatus = GoalStatus.PROPOSED
    parent_goal_id: Optional[str] = None
    subgoal_ids: List[str] = field(default_factory=list)
    tasks: List[GoalTask] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    target_date: Optional[str] = None
    completion_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    progress: float = 0.0

    def __post_init__(self):
        # Normalize enums if strings are provided
        if isinstance(self.goal_type, str):
            try:
                self.goal_type = GoalType(self.goal_type)
            except ValueError:
                raise GoalValidationError(f"Invalid goal_type: {self.goal_type}. Must be one of {[e.value for e in GoalType]}.")
        if isinstance(self.status, str):
            try:
                self.status = GoalStatus(self.status)
            except ValueError:
                raise GoalValidationError(f"Invalid status: {self.status}. Must be one of {[e.value for e in GoalStatus]}.")

        # Normalize tasks to GoalTask objects if dictionaries
        normalized_tasks: List[GoalTask] = []
        for t in self.tasks:
            if isinstance(t, dict):
                normalized_tasks.append(GoalTask.from_dict(t))
            elif isinstance(t, GoalTask):
                normalized_tasks.append(t)
            else:
                raise GoalValidationError(f"Invalid task item: {t}. Must be GoalTask or dict.")
        self.tasks = normalized_tasks

        self.validate()

    def validate(self):
        """Validates all internal constraints for this individual Goal model."""
        if not self.goal_id or not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise GoalValidationError("Goal goal_id must be a non-empty string.")
        if not self.title or not isinstance(self.title, str) or not self.title.strip():
            raise GoalValidationError("Goal title must be a non-empty string.")
        if not isinstance(self.description, str):
            raise GoalValidationError("Goal description must be a string.")
        if not isinstance(self.goal_type, GoalType):
            raise GoalValidationError(f"goal_type must be a valid GoalType enum, got: {self.goal_type}")
        if not isinstance(self.status, GoalStatus):
            raise GoalValidationError(f"status must be a valid GoalStatus enum, got: {self.status}")

        # Progress bounds
        if not isinstance(self.progress, (int, float)):
            raise GoalValidationError("Goal progress must be a numeric value.")
        if self.progress < 0.0 or self.progress > 1.0:
            raise GoalValidationError(f"Goal progress must be between 0.0 and 1.0, got {self.progress}")

        # Timestamps
        if self.created_at <= 0 or self.updated_at <= 0:
            raise GoalValidationError("Timestamps created_at and updated_at must be positive numbers.")
        if self.updated_at < self.created_at:
            raise GoalValidationError("updated_at cannot be prior to created_at.")

        # Target date validation (ISO-8601: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        if self.target_date:
            self._validate_target_date(self.target_date)

        # Self-parent check
        if self.parent_goal_id and self.parent_goal_id == self.goal_id:
            raise GoalValidationError(f"Goal {self.goal_id} cannot be its own parent.")

        # Subgoals uniqueness & self-containment check
        if len(self.subgoal_ids) != len(set(self.subgoal_ids)):
            raise GoalValidationError(f"Duplicate subgoal_ids detected in goal {self.goal_id}: {self.subgoal_ids}")
        if self.goal_id in self.subgoal_ids:
            raise GoalValidationError(f"Goal {self.goal_id} cannot contain itself in subgoal_ids.")

        # Task uniqueness
        task_ids = [t.task_id for t in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise GoalValidationError(f"Duplicate task IDs detected within goal {self.goal_id}: {task_ids}")

        # Task validation
        for task in self.tasks:
            task.validate()

        # Completion criteria validation
        if not isinstance(self.completion_criteria, list):
            raise GoalValidationError("completion_criteria must be a list of strings.")
        for crit in self.completion_criteria:
            if not isinstance(crit, str) or not crit.strip():
                raise GoalValidationError("Each completion criterion must be a non-empty string.")

    @staticmethod
    def _validate_target_date(target_date: str):
        if not isinstance(target_date, str):
            raise GoalValidationError(f"target_date must be an ISO-8601 string, got {type(target_date)}")
        # Check standard ISO formats: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        try:
            datetime.datetime.fromisoformat(target_date.replace("Z", "+00:00"))
        except ValueError:
            raise GoalValidationError(f"target_date '{target_date}' is not a valid ISO-8601 date string.")

    def can_transition_to(self, new_status: GoalStatus) -> bool:
        """Determines if the goal can transition to new_status based on transition rules."""
        if self.status == new_status:
            return True
        allowed = ALLOWED_STATUS_TRANSITIONS.get(self.status, set())
        return new_status in allowed

    def transition_to(self, new_status: Union[GoalStatus, str], force: bool = False):
        """
        Transitions the goal to a new status.
        Raises GoalValidationError if the transition is prohibited.
        """
        if isinstance(new_status, str):
            try:
                new_status = GoalStatus(new_status)
            except ValueError:
                raise GoalValidationError(f"Unknown status: {new_status}")

        if self.status == new_status:
            return

        # Prohibit direct transition from CANCELLED to COMPLETED under any circumstance
        if self.status == GoalStatus.CANCELLED and new_status == GoalStatus.COMPLETED:
            raise GoalValidationError("Illegal transition: cannot transition directly from CANCELLED to COMPLETED.")

        if not force and not self.can_transition_to(new_status):
            raise GoalValidationError(
                f"Prohibited status transition: cannot transition from {self.status.value} to {new_status.value}."
            )

        self.status = new_status
        self.updated_at = time.time()

    def update_task_status(self, task_id: str, completed: bool):
        """Updates the completion state of an internal task."""
        found = False
        for task in self.tasks:
            if task.task_id == task_id:
                task.completed = completed
                if completed:
                    task.completed_at = time.time()
                else:
                    task.completed_at = None
                found = True
                break
        if not found:
            raise GoalValidationError(f"Task with ID '{task_id}' not found in goal '{self.goal_id}'.")
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Serializes Goal to JSON-compatible dictionary."""
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "goal_type": self.goal_type.value,
            "status": self.status.value,
            "parent_goal_id": self.parent_goal_id,
            "subgoal_ids": list(self.subgoal_ids),
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "target_date": self.target_date,
            "completion_criteria": list(self.completion_criteria),
            "metadata": dict(self.metadata),
            "progress": round(float(self.progress), 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        """Deserializes Goal from dictionary with backward-compatible defaults."""
        if not isinstance(data, dict):
            raise GoalValidationError("Goal.from_dict requires a dictionary.")

        raw_tasks = data.get("tasks", [])
        tasks_list = [GoalTask.from_dict(t) if isinstance(t, dict) else t for t in raw_tasks]

        goal = cls(
            goal_id=data.get("goal_id") or f"goal_{uuid.uuid4().hex[:8]}",
            title=data.get("title", ""),
            description=data.get("description", ""),
            goal_type=data.get("goal_type", GoalType.SHORT_TERM),
            status=data.get("status", GoalStatus.PROPOSED),
            parent_goal_id=data.get("parent_goal_id"),
            subgoal_ids=list(data.get("subgoal_ids", [])),
            tasks=tasks_list,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            target_date=data.get("target_date"),
            completion_criteria=list(data.get("completion_criteria", [])),
            metadata=dict(data.get("metadata", {})),
            progress=float(data.get("progress", 0.0)),
        )
        return goal


# =====================================================================
# Hierarchy Integrity & Progress Semantics (Reusable Module Helpers)
# =====================================================================

def validate_hierarchy_acyclic(goals: Dict[str, Goal]) -> None:
    """
    Validates that a collection of goals forms a Directed Acyclic Graph (DAG) of trees.
    Raises GoalValidationError if a circular dependency or dangling reference is found.
    """
    visited: Set[str] = set()
    visiting: Set[str] = set()

    def check_cycle(gid: str, path: List[str]):
        if gid in visiting:
            cycle = " -> ".join(path + [gid])
            raise GoalValidationError(f"Circular goal dependency detected: {cycle}")
        if gid in visited:
            return

        visiting.add(gid)
        goal = goals.get(gid)
        if goal:
            for child_id in goal.subgoal_ids:
                if child_id not in goals:
                    raise GoalValidationError(f"Goal '{gid}' references non-existent child subgoal '{child_id}'.")
                # Also verify child has correct parent pointer if set
                child_goal = goals[child_id]
                if child_goal.parent_goal_id and child_goal.parent_goal_id != gid:
                    raise GoalValidationError(
                        f"Inconsistent hierarchy: Goal '{gid}' claims child '{child_id}', "
                        f"but child's parent_goal_id is '{child_goal.parent_goal_id}'."
                    )
                check_cycle(child_id, path + [gid])

        visiting.remove(gid)
        visited.add(gid)

    for goal_id in goals:
        if goal_id not in visited:
            check_cycle(goal_id, [])


def compute_hierarchical_progress(goal_id: str, goals: Dict[str, Goal]) -> float:
    """
    Calculates deterministic progress for a goal within a goals dictionary.

    Contract:
    1. An empty goal with no tasks and no subgoals has 0.0 progress (not 1.0).
    2. If a goal has only tasks: progress = completed_tasks / total_tasks.
    3. If a goal has only subgoals: progress = sum(subgoal.progress) / len(subgoals).
    4. If a goal has both tasks and subgoals: weighted equally (50% tasks, 50% subgoals):
       progress = 0.5 * (completed_tasks / total_tasks) + 0.5 * (average_subgoal_progress).
    5. A progress value of 1.0 does not automatically mark a goal COMPLETED.
    """
    goal = goals.get(goal_id)
    if not goal:
        return 0.0

    has_tasks = len(goal.tasks) > 0
    has_subgoals = len(goal.subgoal_ids) > 0

    if not has_tasks and not has_subgoals:
        return 0.0

    task_progress = 0.0
    if has_tasks:
        completed = sum(1 for t in goal.tasks if t.completed)
        task_progress = completed / len(goal.tasks)

    subgoal_progress = 0.0
    if has_subgoals:
        subgoal_values = []
        for sid in goal.subgoal_ids:
            if sid in goals:
                subgoal_values.append(compute_hierarchical_progress(sid, goals))
        if subgoal_values:
            subgoal_progress = sum(subgoal_values) / len(subgoal_values)

    if has_tasks and has_subgoals:
        final_progress = 0.5 * task_progress + 0.5 * subgoal_progress
    elif has_tasks:
        final_progress = task_progress
    else:
        final_progress = subgoal_progress

    return round(float(final_progress), 4)
