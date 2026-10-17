"""
JARVIS X — Goal Management Engine
Authoritative CRUD, lifecycle transitions, hierarchical integrity, progress calculations,
and storage persistence for goals in JARVIS OS.
"""

from typing import Dict, Any, List, Optional, Set, Union
import copy
import json
import logging
import os
import re
import time

from .models import (
    Goal,
    GoalTask,
    GoalType,
    GoalStatus,
    GoalValidationError,
    validate_hierarchy_acyclic,
    compute_hierarchical_progress,
)
from .decomposition import ProposedGoalPlan

logger = logging.getLogger("JARVIS.GoalEngine")


class GoalManagerEngine:
    """
    Core Goal Management Engine.
    Manages in-memory active goals indexed and persisted authoritatively through
    the Markdown Vault / MemoryAPI storage layer (vault/goals/<goal_id>.md)
    with atomic validation, progress roll-ups, and EventBus publications.
    """

    def __init__(
        self,
        memory_api: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        security_proxy: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.memory_api = memory_api
        self.event_bus = event_bus
        self.security = security_proxy
        self.config = config or {}

        # Authoritative in-memory registry of goals {goal_id: Goal}
        self._goals: Dict[str, Goal] = {}

        # Load persisted goals upon startup
        self.load_from_storage()

    # ─────────────────────────────────────────────────────────────
    # Persistence Layer
    # ─────────────────────────────────────────────────────────────

    def load_from_storage(self) -> int:
        """
        Loads all stored goal records from the persistence layer.
        Source of Truth: Markdown Vault (category='goals' in vault/goals/)
        or MemoryAPI note reads.
        """
        self._goals.clear()
        loaded_count = 0

        # Direct VaultManager scan if available
        vault_manager = getattr(self.memory_api, "vault", None) if self.memory_api else None
        if vault_manager:
            goals_dir = os.path.join(vault_manager.vault_root, "goals")
            if os.path.isdir(goals_dir):
                for fname in os.listdir(goals_dir):
                    if fname.endswith(".md"):
                        fpath = os.path.join(goals_dir, fname)
                        note = vault_manager.read_note(fpath)
                        if note:
                            try:
                                g_dict = None
                                # Check if json code block exists in body
                                body = note.get("body", "")
                                json_match = re.search(r"```json\s*([\s\S]*?)\s*```", body)
                                if json_match:
                                    g_dict = json.loads(json_match.group(1).strip())
                                elif "goal_data" in note.get("frontmatter", {}):
                                    raw = note["frontmatter"]["goal_data"]
                                    g_dict = json.loads(raw) if isinstance(raw, str) else raw
                                elif body.strip().startswith("{"):
                                    g_dict = json.loads(body.strip())
                                else:
                                    g_dict = note.get("frontmatter", {})

                                if g_dict:
                                    goal = Goal.from_dict(g_dict)
                                    self._goals[goal.goal_id] = goal
                                    loaded_count += 1
                            except Exception as e:
                                logger.warning(f"Skipping malformed goal record {fname}: {e}")

        # Ensure reciprocal parent-child relationship consistency across all loaded goals
        for gid, g in list(self._goals.items()):
            # 1. If child references parent, parent must contain child in subgoal_ids
            if g.parent_goal_id:
                if g.parent_goal_id in self._goals:
                    p = self._goals[g.parent_goal_id]
                    if gid not in p.subgoal_ids:
                        p.subgoal_ids.append(gid)
                else:
                    logger.warning(f"Goal {gid} points to non-existent parent {g.parent_goal_id}; clearing parent reference.")
                    g.parent_goal_id = None

            # 2. If parent references child, child must exist and point back to parent
            valid_subgoals = []
            for cid in g.subgoal_ids:
                if cid in self._goals:
                    child = self._goals[cid]
                    if child.parent_goal_id != gid:
                        child.parent_goal_id = gid
                    valid_subgoals.append(cid)
                else:
                    logger.warning(f"Goal {gid} references non-existent child {cid}; removing reference.")
            g.subgoal_ids = valid_subgoals

        # Recalculate and validate hierarchy
        try:
            validate_hierarchy_acyclic(self._goals)
        except GoalValidationError as e:
            logger.error(f"Integrity warning on storage reload: {e}")

        logger.info(f"GoalManagerEngine loaded {loaded_count} goals from persistence.")
        return loaded_count

    def _persist_goal(self, goal: Goal) -> bool:
        """
        Persists a single Goal record to the storage tier.
        Stores clean markdown note with YAML frontmatter + JSON payload in vault/goals/.
        """
        if not self.memory_api:
            return True  # Running in in-memory test mode

        try:
            vault_manager = getattr(self.memory_api, "vault", None)
            if not vault_manager:
                return True

            filename = f"{goal.goal_id}.md"
            goal_dict = goal.to_dict()
            json_str = json.dumps(goal_dict, indent=2)

            frontmatter = {
                "title": goal.title,
                "goal_id": goal.goal_id,
                "type": "goal_record",
                "goal_type": goal.goal_type.value,
                "status": goal.status.value,
                "progress": goal.progress,
                "parent_goal_id": goal.parent_goal_id,
                "target_date": goal.target_date,
                "subgoal_count": len(goal.subgoal_ids),
                "task_count": len(goal.tasks),
                "created_at": goal.created_at,
                "updated_at": goal.updated_at,
            }

            body = (
                f"# Goal: {goal.title}\n\n"
                f"**Type:** `{goal.goal_type.value}` | **Status:** `{goal.status.value}` | **Progress:** `{round(goal.progress * 100, 1)}%`\n\n"
                f"## Description\n{goal.description or 'No description provided.'}\n\n"
                f"## Completion Criteria\n"
                + ("\n".join(f"- [ ] {c}" for c in goal.completion_criteria) if goal.completion_criteria else "- Standard verification.")
                + "\n\n## Tasks\n"
                + ("\n".join(f"- [{'x' if t.completed else ' '}] {t.description}" for t in goal.tasks) if goal.tasks else "- No atomic tasks attached.")
                + f"\n\n```json\n{json_str}\n```\n"
            )

            # Store in vault subfolder 'goals'
            vault_manager.write_note(
                folder="goals",
                filename=filename,
                content=body,
                metadata=frontmatter,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist goal '{goal.goal_id}': {e}")
            return False

    def _delete_persisted_goal(self, goal_id: str) -> bool:
        """Removes the markdown goal note from the vault storage."""
        if not self.memory_api:
            return True
        try:
            vault_manager = getattr(self.memory_api, "vault", None)
            if not vault_manager:
                return True
            if hasattr(vault_manager, "_safe_resolve_path"):
                target_path = vault_manager._safe_resolve_path(f"{goal_id}.md", base_folder="goals")
            else:
                target_path = os.path.join(vault_manager.vault_root, "goals", f"{goal_id}.md")
            if os.path.isfile(target_path):
                os.remove(target_path)
            return True
        except Exception as e:
            logger.error(f"Failed to delete goal file '{goal_id}.md': {e}")
            return False


    # ─────────────────────────────────────────────────────────────
    # Security & Authorization Helper
    # ─────────────────────────────────────────────────────────────

    def _authorize_mutation(self, action_name: str, details: str) -> bool:
        """
        Validates permission through SecurityProxy if configured.
        Returns True if authorized, False if denied.
        """
        if not self.security:
            return True

        if hasattr(self.security, "is_dangerous") and self.security.is_dangerous(action_name):
            if hasattr(self.security, "request_confirmation"):
                confirmed = self.security.request_confirmation(action_name, details)
                if not confirmed:
                    logger.warning(f"SecurityProxy DENIED mutation: {action_name} ({details})")
                    return False
        return True

    # ─────────────────────────────────────────────────────────────
    # EventBus Helper
    # ─────────────────────────────────────────────────────────────

    def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """Safely publishes an event on the kernel EventBus."""
        if not self.event_bus:
            return
        try:
            if hasattr(self.event_bus, "publish"):
                import asyncio
                import inspect
                publish_fn = self.event_bus.publish
                if inspect.iscoroutinefunction(publish_fn):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(publish_fn(event_type, data))
                    except RuntimeError:
                        # Fallback for synchronous test harness without active event loop
                        try:
                            asyncio.run(publish_fn(event_type, data))
                        except Exception:
                            pass
                else:
                    publish_fn(event_type, data)
        except Exception as e:
            logger.warning(f"EventBus publication failed for {event_type}: {e}")

    # ─────────────────────────────────────────────────────────────
    # Core Goal CRUD Operations
    # ─────────────────────────────────────────────────────────────

    def create_goal(
        self,
        title: str,
        description: str = "",
        goal_type: Union[GoalType, str] = GoalType.SHORT_TERM,
        status: Union[GoalStatus, str] = GoalStatus.ACTIVE,
        parent_goal_id: Optional[str] = None,
        target_date: Optional[str] = None,
        completion_criteria: Optional[List[str]] = None,
        tasks: Optional[List[Union[GoalTask, Dict[str, Any]]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Goal:
        """Creates, validates, and persists a new Goal."""
        if not title or not title.strip():
            raise GoalValidationError("Goal title cannot be empty.")

        # Security check for creating goal
        if not self._authorize_mutation("create_goal", f"Create goal '{title}'"):
            raise PermissionError("Action 'create_goal' was not authorized by SecurityProxy.")

        # Check parent existence if specified
        if parent_goal_id:
            if parent_goal_id not in self._goals:
                raise GoalValidationError(f"Specified parent goal '{parent_goal_id}' does not exist.")

        goal = Goal(
            title=title.strip(),
            description=description.strip(),
            goal_type=goal_type,
            status=status,
            parent_goal_id=parent_goal_id,
            target_date=target_date,
            completion_criteria=completion_criteria or [],
            tasks=tasks or [],
            metadata=metadata or {},
        )

        # Snapshot in-memory state for rollback on persistence failure
        orig_goals_snapshot = copy.deepcopy(self._goals)

        # Update in-memory registry
        self._goals[goal.goal_id] = goal

        # If parent specified, register in parent's subgoal_ids
        parent_persisted = False
        if parent_goal_id and parent_goal_id in self._goals:
            parent = self._goals[parent_goal_id]
            if goal.goal_id not in parent.subgoal_ids:
                parent.subgoal_ids.append(goal.goal_id)
                parent.updated_at = time.time()
                parent.progress = compute_hierarchical_progress(parent.goal_id, self._goals)
                if not self._persist_goal(parent):
                    self._goals = orig_goals_snapshot
                    raise IOError(f"Failed to persist parent goal '{parent_goal_id}' during child creation.")
                parent_persisted = True

        # Compute initial progress
        goal.progress = compute_hierarchical_progress(goal.goal_id, self._goals)

        # Validate hierarchy integrity
        try:
            validate_hierarchy_acyclic(self._goals)
        except GoalValidationError:
            self._goals = orig_goals_snapshot
            raise

        # Persist goal
        if not self._persist_goal(goal):
            self._goals = orig_goals_snapshot
            if parent_persisted and parent_goal_id in orig_goals_snapshot:
                self._persist_goal(orig_goals_snapshot[parent_goal_id])
            raise IOError(f"Failed to persist newly created goal '{goal.goal_id}'.")

        # Publish event strictly after successful persistence
        self._publish_event("goal_created", {"goal_id": goal.goal_id, "title": goal.title, "status": goal.status.value})

        return goal

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Retrieves a Goal by ID."""
        return self._goals.get(goal_id)

    def list_goals(
        self,
        status: Optional[Union[GoalStatus, str]] = None,
        goal_type: Optional[Union[GoalType, str]] = None,
        parent_id: Optional[str] = None,
        only_root: bool = False,
    ) -> List[Goal]:
        """Returns filtered list of goals."""
        results = list(self._goals.values())

        if status:
            target_status = GoalStatus(status) if isinstance(status, str) else status
            results = [g for g in results if g.status == target_status]

        if goal_type:
            target_type = GoalType(goal_type) if isinstance(goal_type, str) else goal_type
            results = [g for g in results if g.goal_type == target_type]

        if parent_id is not None:
            results = [g for g in results if g.parent_goal_id == parent_id]
        elif only_root:
            results = [g for g in results if g.parent_goal_id is None]

        return results

    def update_goal(self, goal_id: str, updates: Dict[str, Any]) -> Goal:
        """Updates fields of an existing goal with full validation."""
        goal = self._goals.get(goal_id)
        if not goal:
            raise GoalValidationError(f"Goal with ID '{goal_id}' does not exist.")

        # Security check
        if not self._authorize_mutation("update_goal", f"Update goal '{goal.title}'"):
            raise PermissionError("Action 'update_goal' was not authorized by SecurityProxy.")

        # Snapshot in-memory state for rollback on persistence failure
        orig_goals_snapshot = copy.deepcopy(self._goals)

        # Status transition
        if "status" in updates:
            new_status = updates["status"]
            self._transition_goal_status(goal, new_status)

        if "title" in updates:
            new_title = updates["title"]
            if not new_title or not new_title.strip():
                self._goals = orig_goals_snapshot
                raise GoalValidationError("Goal title cannot be empty.")
            goal.title = new_title.strip()

        if "description" in updates:
            goal.description = str(updates["description"]).strip()

        if "target_date" in updates:
            t_date = updates["target_date"]
            if t_date:
                try:
                    Goal._validate_target_date(t_date)
                except GoalValidationError:
                    self._goals = orig_goals_snapshot
                    raise
            goal.target_date = t_date

        if "completion_criteria" in updates:
            goal.completion_criteria = list(updates["completion_criteria"])

        if "metadata" in updates and isinstance(updates["metadata"], dict):
            goal.metadata.update(updates["metadata"])

        goal.updated_at = time.time()
        goal.progress = compute_hierarchical_progress(goal.goal_id, self._goals)

        try:
            validate_hierarchy_acyclic(self._goals)
        except GoalValidationError:
            self._goals = orig_goals_snapshot
            raise

        if not self._persist_goal(goal):
            self._goals = orig_goals_snapshot
            raise IOError(f"Failed to persist updated goal '{goal.goal_id}'.")

        # Propagate progress recalculation to parent
        self._recalculate_ancestor_progress(goal.parent_goal_id)

        # Publish event strictly after successful persistence
        self._publish_event("goal_updated", {"goal_id": goal.goal_id, "status": goal.status.value, "progress": goal.progress})
        return goal

    def pause_goal(self, goal_id: str) -> Goal:
        """Transitions goal to PAUSED."""
        return self.update_goal(goal_id, {"status": GoalStatus.PAUSED})

    def resume_goal(self, goal_id: str) -> Goal:
        """Transitions goal from PAUSED to ACTIVE."""
        return self.update_goal(goal_id, {"status": GoalStatus.ACTIVE})

    def complete_goal(self, goal_id: str, force: bool = False) -> Goal:
        """
        Marks goal as COMPLETED.
        Validates that all tasks and child goals are complete unless force=True.
        """
        goal = self._goals.get(goal_id)
        if not goal:
            raise GoalValidationError(f"Goal '{goal_id}' not found.")

        # Security check
        if not self._authorize_mutation("complete_goal", f"Complete goal '{goal.title}'"):
            raise PermissionError("Action 'complete_goal' was not authorized by SecurityProxy.")

        # Check incomplete tasks
        incomplete_tasks = [t for t in goal.tasks if not t.completed]
        if incomplete_tasks and not force:
            raise GoalValidationError(
                f"Cannot complete goal '{goal.title}': {len(incomplete_tasks)} task(s) remain incomplete."
            )

        # Check incomplete subgoals
        incomplete_subgoals = [
            sid for sid in goal.subgoal_ids
            if sid in self._goals and self._goals[sid].status != GoalStatus.COMPLETED
        ]
        if incomplete_subgoals and not force:
            raise GoalValidationError(
                f"Cannot complete goal '{goal.title}': {len(incomplete_subgoals)} child subgoal(s) remain incomplete."
            )

        # Snapshot in-memory state for rollback on persistence failure
        orig_goals_snapshot = copy.deepcopy(self._goals)

        goal.transition_to(GoalStatus.COMPLETED)
        goal.progress = 1.0
        goal.updated_at = time.time()

        if not self._persist_goal(goal):
            self._goals = orig_goals_snapshot
            raise IOError(f"Failed to persist completed goal '{goal.goal_id}'.")

        self._recalculate_ancestor_progress(goal.parent_goal_id)
        # Publish event strictly after successful persistence
        self._publish_event("goal_completed", {"goal_id": goal.goal_id, "title": goal.title})
        return goal

    def cancel_goal(self, goal_id: str, preserve_children: bool = True) -> Goal:
        """
        Cancels a goal.
        Preserves child subgoals as independent goals (or cascades cancellation).
        """
        goal = self._goals.get(goal_id)
        if not goal:
            raise GoalValidationError(f"Goal '{goal_id}' not found.")

        if not self._authorize_mutation("cancel_goal", f"Cancel goal '{goal.title}'"):
            raise PermissionError("Action 'cancel_goal' was not authorized by SecurityProxy.")

        # Snapshot in-memory state for rollback on persistence failure
        orig_goals_snapshot = copy.deepcopy(self._goals)

        goal.transition_to(GoalStatus.CANCELLED)
        goal.updated_at = time.time()

        # Handle child subgoals
        persisted_children = []
        try:
            for sid in list(goal.subgoal_ids):
                child = self._goals.get(sid)
                if child:
                    if preserve_children:
                        # Detach child from parent
                        child.parent_goal_id = None
                        child.updated_at = time.time()
                        if not self._persist_goal(child):
                            raise IOError(f"Failed to persist detached child goal '{child.goal_id}'.")
                    else:
                        # Cascade cancel
                        child.transition_to(GoalStatus.CANCELLED)
                        if not self._persist_goal(child):
                            raise IOError(f"Failed to persist cancelled child goal '{child.goal_id}'.")
                    persisted_children.append(child)

            if not self._persist_goal(goal):
                raise IOError(f"Failed to persist cancelled goal '{goal.goal_id}'.")
        except Exception:
            self._goals = orig_goals_snapshot
            # Revert any written child files
            for c in persisted_children:
                if c.goal_id in orig_goals_snapshot:
                    self._persist_goal(orig_goals_snapshot[c.goal_id])
            raise

        self._recalculate_ancestor_progress(goal.parent_goal_id)
        # Publish event strictly after successful persistence
        self._publish_event("goal_cancelled", {"goal_id": goal.goal_id, "title": goal.title})
        return goal

    def add_subgoal(self, parent_id: str, child_id: str) -> None:
        """Links an existing child goal to a parent goal."""
        parent = self._goals.get(parent_id)
        child = self._goals.get(child_id)
        if not parent or not child:
            raise GoalValidationError("Both parent and child goal must exist.")

        if not self._authorize_mutation("add_subgoal", f"Add subgoal '{child.title}' to parent '{parent.title}'"):
            raise PermissionError("Action 'add_subgoal' was not authorized by SecurityProxy.")

        if child.parent_goal_id and child.parent_goal_id != parent_id:
            raise GoalValidationError(f"Child goal '{child_id}' is already linked to parent '{child.parent_goal_id}'.")

        orig_parent_subgoals = list(parent.subgoal_ids)
        orig_parent_progress = parent.progress
        orig_parent_updated = parent.updated_at
        orig_child_parent = child.parent_goal_id
        orig_child_updated = child.updated_at

        if child_id not in parent.subgoal_ids:
            parent.subgoal_ids.append(child_id)
        child.parent_goal_id = parent_id

        # Check cycle before persisting; rollback on failure
        try:
            validate_hierarchy_acyclic(self._goals)
        except GoalValidationError:
            parent.subgoal_ids = orig_parent_subgoals
            parent.progress = orig_parent_progress
            parent.updated_at = orig_parent_updated
            child.parent_goal_id = orig_child_parent
            child.updated_at = orig_child_updated
            raise

        parent.progress = compute_hierarchical_progress(parent_id, self._goals)
        parent.updated_at = time.time()
        child.updated_at = time.time()

        if not self._persist_goal(parent) or not self._persist_goal(child):
            parent.subgoal_ids = orig_parent_subgoals
            parent.progress = orig_parent_progress
            parent.updated_at = orig_parent_updated
            child.parent_goal_id = orig_child_parent
            child.updated_at = orig_child_updated
            self._persist_goal(parent)
            self._persist_goal(child)
            raise IOError(f"Failed to persist parent-child link between '{parent_id}' and '{child_id}'.")

        self._publish_event("goal_subgoal_added", {"parent_id": parent_id, "child_id": child_id})

    def remove_subgoal(self, parent_id: str, child_id: str) -> None:
        """Detaches a child subgoal from its parent."""
        parent = self._goals.get(parent_id)
        child = self._goals.get(child_id)
        if not parent or not child:
            raise GoalValidationError("Both parent and child goal must exist.")

        if not self._authorize_mutation("remove_subgoal", f"Remove subgoal '{child.title}' from parent '{parent.title}'"):
            raise PermissionError("Action 'remove_subgoal' was not authorized by SecurityProxy.")

        orig_parent_subgoals = list(parent.subgoal_ids)
        orig_parent_progress = parent.progress
        orig_parent_updated = parent.updated_at
        orig_child_parent = child.parent_goal_id
        orig_child_updated = child.updated_at

        if child_id in parent.subgoal_ids:
            parent.subgoal_ids.remove(child_id)
        if child.parent_goal_id == parent_id:
            child.parent_goal_id = None

        parent.progress = compute_hierarchical_progress(parent_id, self._goals)
        parent.updated_at = time.time()
        child.updated_at = time.time()

        if not self._persist_goal(parent) or not self._persist_goal(child):
            parent.subgoal_ids = orig_parent_subgoals
            parent.progress = orig_parent_progress
            parent.updated_at = orig_parent_updated
            child.parent_goal_id = orig_child_parent
            child.updated_at = orig_child_updated
            self._persist_goal(parent)
            self._persist_goal(child)
            raise IOError(f"Failed to persist subgoal removal between '{parent_id}' and '{child_id}'.")

        self._publish_event("goal_subgoal_removed", {"parent_id": parent_id, "child_id": child_id})

    def calculate_progress(self, goal_id: str) -> float:
        """Calculates and updates current progress for goal_id."""
        goal = self._goals.get(goal_id)
        if not goal:
            raise GoalValidationError(f"Goal '{goal_id}' not found.")
        prog = compute_hierarchical_progress(goal_id, self._goals)
        goal.progress = prog
        self._persist_goal(goal)
        return prog

    def _recalculate_ancestor_progress(self, parent_id: Optional[str]):
        """Recursively recalculates progress upwards towards root."""
        curr = parent_id
        while curr and curr in self._goals:
            p = self._goals[curr]
            p.progress = compute_hierarchical_progress(p.goal_id, self._goals)
            self._persist_goal(p)
            curr = p.parent_goal_id

    def _transition_goal_status(self, goal: Goal, new_status: Union[GoalStatus, str]):
        """Handles explicit status transitions with reopen logic."""
        target = GoalStatus(new_status) if isinstance(new_status, str) else new_status
        if goal.status == target:
            return

        # If reopening a COMPLETED goal, recalculate progress
        if goal.status == GoalStatus.COMPLETED and target == GoalStatus.ACTIVE:
            goal.transition_to(target)
            goal.progress = compute_hierarchical_progress(goal.goal_id, self._goals)
            return

        goal.transition_to(target)

    # ─────────────────────────────────────────────────────────────
    # Hierarchy & Summarization
    # ─────────────────────────────────────────────────────────────

    def get_goal_hierarchy(self, root_goal_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Builds recursive tree representations of goal hierarchies.
        If root_goal_id is provided, returns subtree for that goal.
        Otherwise, returns trees for all root-level goals.
        """
        def build_node(g: Goal) -> Dict[str, Any]:
            children = [
                build_node(self._goals[sid])
                for sid in g.subgoal_ids
                if sid in self._goals
            ]
            return {
                "goal_id": g.goal_id,
                "title": g.title,
                "goal_type": g.goal_type.value,
                "status": g.status.value,
                "progress": g.progress,
                "tasks_count": len(g.tasks),
                "completed_tasks": sum(1 for t in g.tasks if t.completed),
                "subgoals": children,
            }

        if root_goal_id:
            root = self._goals.get(root_goal_id)
            if not root:
                return []
            return [build_node(root)]

        roots = [g for g in self._goals.values() if g.parent_goal_id is None]
        return [build_node(r) for r in roots]

    def get_active_goals_summary(self) -> Dict[str, Any]:
        """Provides an executive overview of all active, paused, and proposed goals."""
        active = [g for g in self._goals.values() if g.status == GoalStatus.ACTIVE]
        paused = [g for g in self._goals.values() if g.status == GoalStatus.PAUSED]
        proposed = [g for g in self._goals.values() if g.status == GoalStatus.PROPOSED]
        completed = [g for g in self._goals.values() if g.status == GoalStatus.COMPLETED]

        return {
            "total_goals": len(self._goals),
            "active_count": len(active),
            "paused_count": len(paused),
            "proposed_count": len(proposed),
            "completed_count": len(completed),
            "active_goals": [
                {
                    "goal_id": g.goal_id,
                    "title": g.title,
                    "type": g.goal_type.value,
                    "progress": round(g.progress * 100, 1),
                    "subgoals": len(g.subgoal_ids),
                    "target_date": g.target_date,
                }
                for g in active
            ],
        }

    # ─────────────────────────────────────────────────────────────
    # ProposedGoalPlan Approval & Persistence
    # ─────────────────────────────────────────────────────────────

    def save_approved_plan(
        self,
        plan: ProposedGoalPlan,
        force_unresolved_clarifications: bool = False,
    ) -> Goal:
        """
        Persists a ProposedGoalPlan after explicit approval.
        - Refuses persistence if clarification questions are unresolved (unless forced).
        - Transitions root and all subgoals to ACTIVE state.
        - NEVER authorizes or triggers autonomous task execution.
        """
        if plan.approved is False:
            raise GoalValidationError("Cannot persist a rejected ProposedGoalPlan.")

        # Check for unresolved clarifications
        if plan.clarification_questions and not force_unresolved_clarifications and plan.approved is None:
            raise GoalValidationError(
                f"Cannot approve plan: {len(plan.clarification_questions)} clarification questions remain unresolved."
            )

        root = plan.root_goal
        # Prevent duplicate insertion
        if root.goal_id in self._goals:
            raise GoalValidationError(f"Goal '{root.goal_id}' is already registered.")

        # Security check
        if not self._authorize_mutation("save_approved_plan", f"Approve and persist goal plan '{root.title}'"):
            raise PermissionError("Action 'save_approved_plan' was not authorized by SecurityProxy.")

        # Mark plan approved
        plan.approve()

        orig_goals_snapshot = copy.deepcopy(self._goals)

        # Register root
        self._goals[root.goal_id] = root

        # Register each subgoal
        persisted_subgoals = []
        try:
            for sg in plan.subgoals:
                sg.parent_goal_id = root.goal_id
                self._goals[sg.goal_id] = sg
                if not self._persist_goal(sg):
                    raise IOError(f"Failed to persist subgoal '{sg.goal_id}'.")
                persisted_subgoals.append(sg)

            root.subgoal_ids = [sg.goal_id for sg in plan.subgoals]
            root.progress = compute_hierarchical_progress(root.goal_id, self._goals)

            validate_hierarchy_acyclic(self._goals)
            if not self._persist_goal(root):
                raise IOError(f"Failed to persist root goal '{root.goal_id}'.")
        except Exception:
            self._goals = orig_goals_snapshot
            for sg in persisted_subgoals:
                self._delete_persisted_goal(sg.goal_id)
            self._delete_persisted_goal(root.goal_id)
            raise

        # Publish event strictly after successful persistence
        self._publish_event("goal_plan_approved", {"root_goal_id": root.goal_id, "subgoals_count": len(plan.subgoals)})
        return root
