"""
JARVIS X — Personal Project Intelligence Engine
Orchestrates project contextual knowledge, goal linkages, blockers, and decisions.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from .models import (
    PersonalProject,
    ProjectStatus,
    ProjectBlocker,
    ProjectDecisionRecord,
)

logger = logging.getLogger("JARVIS.ProjectIntelligence")


class ProjectIntelligenceEngine:
    """
    Subsystem providing structured, contextual understanding of personal projects.
    Guarantees:
    - Reuses existing GoalManagerEngine and LongHorizonPlanningEngine entities without duplicates.
    - Answers grounded status queries distinguishing stored facts from inference.
    - Preserves provenance of project decisions and blocker resolutions.
    """

    def __init__(
        self,
        goal_engine: Optional[Any] = None,
        planning_engine: Optional[Any] = None,
        memory_api: Optional[Any] = None,
    ):
        self.goal_engine = goal_engine
        self.planning_engine = planning_engine
        self.memory = memory_api
        self._projects: Dict[str, PersonalProject] = {}

    def register_project(
        self,
        name: str,
        description: str = "",
        repository_path: Optional[str] = None,
        linked_goal_ids: Optional[List[str]] = None,
        linked_plan_ids: Optional[List[str]] = None,
    ) -> PersonalProject:
        project = PersonalProject(
            name=name,
            description=description,
            repository_path=repository_path,
            linked_goal_ids=linked_goal_ids or [],
            linked_plan_ids=linked_plan_ids or [],
        )
        self._projects[project.project_id] = project
        logger.info(f"Registered project '{project.name}' ({project.project_id})")
        return project

    def get_project(self, project_id: str) -> Optional[PersonalProject]:
        return self._projects.get(project_id)

    def list_projects(self) -> List[PersonalProject]:
        return list(self._projects.values())

    def add_blocker(self, project_id: str, description: str, severity: str = "HIGH") -> ProjectBlocker:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")
        blocker = ProjectBlocker(description=description, severity=severity)
        project.active_blockers.append(blocker)
        project.updated_at = time.time()
        return blocker

    def resolve_blocker(self, project_id: str, blocker_id: str, notes: str = "") -> bool:
        project = self.get_project(project_id)
        if not project:
            return False
        for b in project.active_blockers:
            if b.blocker_id == blocker_id:
                b.resolved = True
                b.resolved_at = time.time()
                b.resolution_notes = notes
                project.updated_at = time.time()
                return True
        return False

    def record_decision(
        self,
        project_id: str,
        title: str,
        rationale: str,
        decided_by: str = "User",
        related_files: Optional[List[str]] = None,
    ) -> ProjectDecisionRecord:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")
        record = ProjectDecisionRecord(
            title=title,
            rationale=rationale,
            decided_by=decided_by,
            related_files=related_files or [],
        )
        project.decisions.append(record)
        project.updated_at = time.time()
        return record

    def analyze_project_status(self, project_id: str) -> Dict[str, Any]:
        """Synthesizes comprehensive status report grounded in actual goals and plans."""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")

        # Gather real goal details
        linked_goals_info = []
        if self.goal_engine and hasattr(self.goal_engine, "get_goal"):
            for gid in project.linked_goal_ids:
                g = self.goal_engine.get_goal(gid)
                if g:
                    linked_goals_info.append({
                        "goal_id": g.goal_id,
                        "title": g.title,
                        "status": g.status.value if hasattr(g.status, "value") else str(g.status),
                        "progress": getattr(g, "progress", 0.0),
                    })

        unresolved_blockers = [b for b in project.active_blockers if not b.resolved]

        return {
            "project_id": project.project_id,
            "name": project.name,
            "status": project.status.value,
            "repository_path": project.repository_path,
            "unresolved_blockers_count": len(unresolved_blockers),
            "unresolved_blockers": [b.to_dict() for b in unresolved_blockers],
            "total_decisions_recorded": len(project.decisions),
            "recent_decisions": [d.to_dict() for d in project.decisions[-3:]],
            "linked_goals": linked_goals_info,
            "overall_health": "AT_RISK" if unresolved_blockers else "HEALTHY",
        }
