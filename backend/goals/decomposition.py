"""
JARVIS X — Goal Decomposition Engine
Decomposes high-level goals into hierarchical subgoals and atomic actionable tasks
using provider-agnostic LLMs with deterministic structured fallback and approval workflows.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
import json
import logging
import re
import time
import uuid

from .models import (
    Goal,
    GoalTask,
    GoalType,
    GoalStatus,
    GoalValidationError,
)

logger = logging.getLogger("JARVIS.GoalDecomposition")

DECOMPOSITION_SYSTEM_PROMPT = """You are the JARVIS Goal Decomposition Engine.
Your task is to decompose a user's high-level goal into a structured, actionable plan.

Return your response strictly as valid JSON matching this schema:
{
  "goal_type": "SHORT_TERM" | "MEDIUM_TERM" | "LONG_TERM",
  "completion_criteria": ["criterion 1", "criterion 2"],
  "assumptions": ["assumption 1"],
  "ambiguities": ["ambiguity 1"],
  "clarification_questions": ["question 1"],
  "subgoals": [
    {
      "title": "Subgoal title",
      "description": "Subgoal description",
      "goal_type": "SHORT_TERM" | "MEDIUM_TERM",
      "completion_criteria": ["measurable result 1"],
      "tasks": [
        {
          "description": "Concrete actionable task",
          "assigned_skill": "coding" | "browser" | "system" | "plan" | null
        }
      ]
    }
  ]
}

Guidelines:
1. Provide 2 to 5 coherent, non-redundant subgoals.
2. Every task must be concrete and actionable (avoid vague placeholders like 'work on project').
3. Completion criteria must be measurable outcomes.
4. If essential information is missing, list clear clarification questions and ambiguities.
5. Do NOT include Markdown formatting or backticks; output raw JSON only.
"""


@dataclass
class ProposedGoalPlan:
    """
    Holds a proposed decomposition plan awaiting user approval.
    Does not execute tasks or activate goals automatically.
    """
    plan_id: str = field(default_factory=lambda: f"gplan_{uuid.uuid4().hex[:8]}")
    root_goal: Goal = field(default_factory=lambda: Goal(title="Untitled Goal"))
    subgoals: List[Goal] = field(default_factory=list)
    completion_criteria: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    ambiguities: List[str] = field(default_factory=list)
    clarification_questions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "llm"  # "llm" or "fallback"
    approved: Optional[bool] = None  # None = pending, True = approved, False = rejected
    reviewed_at: Optional[float] = None

    def approve(self) -> None:
        """User explicitly approves the proposal."""
        self.approved = True
        self.reviewed_at = time.time()
        self.root_goal.status = GoalStatus.ACTIVE
        for sg in self.subgoals:
            sg.status = GoalStatus.ACTIVE

    def reject(self, reason: Optional[str] = None) -> None:
        """User explicitly rejects the proposal."""
        self.approved = False
        self.reviewed_at = time.time()
        self.root_goal.status = GoalStatus.CANCELLED
        for sg in self.subgoals:
            sg.status = GoalStatus.CANCELLED
        if reason:
            self.metadata["rejection_reason"] = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "root_goal": self.root_goal.to_dict(),
            "subgoals": [sg.to_dict() for sg in self.subgoals],
            "completion_criteria": list(self.completion_criteria),
            "assumptions": list(self.assumptions),
            "ambiguities": list(self.ambiguities),
            "clarification_questions": list(self.clarification_questions),
            "metadata": dict(self.metadata),
            "source": self.source,
            "approved": self.approved,
            "reviewed_at": self.reviewed_at,
        }


class GoalDecompositionEngine:
    """
    Intelligent Decomposition Engine for breaking broad goals into hierarchical subgoals and tasks.
    Integrates with LLMClient or any LLM provider adapter, featuring deterministic fallback.
    """

    def __init__(self, llm_client: Optional[Any] = None, config: Optional[Dict[str, Any]] = None):
        self.llm = llm_client
        self.config = config or {}
        self.default_timeout = self.config.get("decomposition_timeout", 15.0)

    async def decompose_goal(
        self,
        title: str,
        description: str = "",
        context: Optional[str] = None,
        target_date: Optional[str] = None,
        depth: int = 1,
    ) -> ProposedGoalPlan:
        """
        Decomposes a goal into a ProposedGoalPlan.
        Returns a proposal in PROPOSED state (never automatically active or executed).
        """
        if not title or not title.strip():
            raise GoalValidationError("Cannot decompose goal: title is empty.")

        title = title.strip()
        description = (description or "").strip()

        # Check for ambiguity
        ambiguities, clarification_questions = self._detect_ambiguities(title, description)

        # Attempt LLM decomposition if client is provided and available
        plan = None
        if self.llm is not None:
            try:
                plan = await self._decompose_with_llm(
                    title=title,
                    description=description,
                    context=context,
                    target_date=target_date,
                    ambiguities=ambiguities,
                    clarification_questions=clarification_questions,
                )
            except Exception as e:
                logger.warning(f"LLM decomposition failed: {e}. Reverting to deterministic fallback.")
                plan = None

        if plan is None:
            plan = self._decompose_fallback(
                title=title,
                description=description,
                context=context,
                target_date=target_date,
                ambiguities=ambiguities,
                clarification_questions=clarification_questions,
            )

        return plan

    def _detect_ambiguities(self, title: str, description: str) -> tuple[List[str], List[str]]:
        """Identifies broad, vague, or missing critical parameters."""
        ambiguities = []
        questions = []
        full_text = f"{title} {description}".lower()

        # Very short titles
        if len(title.split()) <= 2 and not description:
            ambiguities.append("Goal description is extremely brief without concrete scope.")
            questions.append(f"What specific scope or target deliverables do you envision for '{title}'?")

        # Common underspecified keywords
        if any(w in full_text for w in ["learn", "master", "study"]) and not any(w in full_text for w in ["by", "course", "project", "exam", "certification"]):
            ambiguities.append("No curriculum, timeframe, or target competency metric specified.")
            questions.append("Is there a specific certification, timeline, or practical project you want to complete?")

        if any(w in full_text for w in ["build", "create", "make", "develop"]) and not any(w in full_text for w in ["stack", "python", "react", "app", "web", "tool", "mvp"]):
            ambiguities.append("Technology stack or platform architecture not defined.")
            questions.append("What technologies, platforms, or tools should be used for this project?")

        return ambiguities, questions

    async def _decompose_with_llm(
        self,
        title: str,
        description: str,
        context: Optional[str],
        target_date: Optional[str],
        ambiguities: List[str],
        clarification_questions: List[str],
    ) -> ProposedGoalPlan:
        """Invokes LLM client to generate structured plan and validates against schema."""
        user_prompt = f"Goal Title: {title}\nDescription: {description or 'N/A'}\n"
        if context:
            user_prompt += f"Context: {context}\n"
        if target_date:
            user_prompt += f"Target Date: {target_date}\n"

        messages = [
            {"role": "system", "content": DECOMPOSITION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Check client capability
        response_text = ""
        if hasattr(self.llm, "chat_sync"):
            response_text = self.llm.chat_sync(messages)
        elif hasattr(self.llm, "chat"):
            resp = self.llm.chat(messages)
            response_text = resp if isinstance(resp, str) else getattr(resp, "content", "")
        else:
            raise RuntimeError("LLM client does not support standard chat interfaces.")

        if not response_text or not response_text.strip():
            raise ValueError("LLM returned an empty response.")

        raw_json = self._extract_json(response_text)
        data = json.loads(raw_json)

        return self._build_plan_from_dict(
            title=title,
            description=description,
            target_date=target_date,
            data=data,
            source="llm",
            initial_ambiguities=ambiguities,
            initial_questions=clarification_questions,
        )

    def _extract_json(self, text: str) -> str:
        """Strips markdown code fences and extracts the outer JSON object."""
        text = text.strip()
        # Remove markdown fences
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if fence_match:
            text = fence_match.group(1).strip()
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    def _decompose_fallback(
        self,
        title: str,
        description: str,
        context: Optional[str],
        target_date: Optional[str],
        ambiguities: List[str],
        clarification_questions: List[str],
    ) -> ProposedGoalPlan:
        """Deterministic heuristic decomposition when LLM is unavailable."""
        lower_title = title.lower()
        subgoals_data = []

        if any(w in lower_title for w in ["learn", "study", "master"]):
            gtype = GoalType.LONG_TERM if "master" in lower_title else GoalType.MEDIUM_TERM
            criteria = [
                f"Complete foundational study for {title}",
                f"Build a practical demonstration project for {title}",
                "Document learning notes and summary in vault",
            ]
            subgoals_data = [
                {
                    "title": f"1. Research and Fundamentals ({title})",
                    "description": "Establish baseline conceptual knowledge and gather authoritative resources.",
                    "tasks": [
                        {"description": f"Gather top reference documentation and tutorials for {title}", "assigned_skill": "browser"},
                        {"description": "Synthesize core terminology and concepts into vault study note", "assigned_skill": "plan"},
                    ],
                    "completion_criteria": ["Foundational notes created in knowledge vault"],
                },
                {
                    "title": f"2. Hands-on Practice & Implementation ({title})",
                    "description": "Apply learned principles by building focused proof-of-concepts.",
                    "tasks": [
                        {"description": f"Develop minimal working exercises applying {title}", "assigned_skill": "coding"},
                        {"description": "Test and troubleshoot errors encountered during practice", "assigned_skill": "system"},
                    ],
                    "completion_criteria": ["Working practice code verified and executing"],
                },
                {
                    "title": f"3. Synthesis & Evaluation ({title})",
                    "description": "Validate acquired competency and consolidate learnings.",
                    "tasks": [
                        {"description": "Conduct self-assessment against primary learning criteria", "assigned_skill": "plan"},
                        {"description": "Write final project summary note in Obsidian vault", "assigned_skill": "plan"},
                    ],
                    "completion_criteria": ["All learning milestones achieved and documented"],
                },
            ]
        elif any(w in lower_title for w in ["build", "create", "develop", "implement"]):
            gtype = GoalType.LONG_TERM if any(w in lower_title for w in ["system", "platform", "production", "os", "assistant", "ai"]) else GoalType.MEDIUM_TERM
            criteria = [
                f"Deliver fully functional implementation of {title}",
                "Validate 100% test pass rate and stability",
                "Complete technical documentation and deployment guide",
            ]
            subgoals_data = [
                {
                    "title": f"1. Architectural Design & Scaffolding",
                    "description": "Define component interfaces, dependencies, and core models.",
                    "tasks": [
                        {"description": f"Draft architecture specifications and data models for {title}", "assigned_skill": "plan"},
                        {"description": "Scaffold directory structure and initial module interfaces", "assigned_skill": "coding"},
                    ],
                    "completion_criteria": ["Architecture spec approved and initial package created"],
                },
                {
                    "title": f"2. Core Implementation",
                    "description": "Implement primary features and execution pipelines.",
                    "tasks": [
                        {"description": f"Implement core logic and subsystem engines for {title}", "assigned_skill": "coding"},
                        {"description": "Integrate error handling, security checks, and boundaries", "assigned_skill": "coding"},
                    ],
                    "completion_criteria": ["Core components implemented and integrated"],
                },
                {
                    "title": f"3. Verification, Testing & Documentation",
                    "description": "Ensure reliability with automated test suites and architectural documentation.",
                    "tasks": [
                        {"description": "Write and run comprehensive unit and integration tests", "assigned_skill": "coding"},
                        {"description": "Create architectural guide and update system documentation", "assigned_skill": "plan"},
                    ],
                    "completion_criteria": ["All test suites passing with zero failures"],
                },
            ]
        else:
            gtype = GoalType.SHORT_TERM
            criteria = [
                f"Successfully achieve objective: {title}",
                "Review outcomes and record completion status",
            ]
            subgoals_data = [
                {
                    "title": f"1. Discovery & Planning",
                    "description": "Clarify requirements and break down immediate steps.",
                    "tasks": [
                        {"description": f"Define success criteria and gather prerequisites for {title}", "assigned_skill": "plan"},
                    ],
                    "completion_criteria": ["Prerequisites identified and verified"],
                },
                {
                    "title": f"2. Execution & Finalization",
                    "description": "Perform necessary actions and verify results.",
                    "tasks": [
                        {"description": f"Execute action items required for {title}", "assigned_skill": "system"},
                        {"description": "Verify task results and close out objective", "assigned_skill": "plan"},
                    ],
                    "completion_criteria": ["Actions executed and verified"],
                },
            ]

        data = {
            "goal_type": gtype.value,
            "completion_criteria": criteria,
            "assumptions": ["Deterministic fallback applied due to unavailable LLM provider."],
            "ambiguities": ambiguities,
            "clarification_questions": clarification_questions,
            "subgoals": subgoals_data,
        }

        return self._build_plan_from_dict(
            title=title,
            description=description,
            target_date=target_date,
            data=data,
            source="fallback",
            initial_ambiguities=ambiguities,
            initial_questions=clarification_questions,
        )

    def _build_plan_from_dict(
        self,
        title: str,
        description: str,
        target_date: Optional[str],
        data: Dict[str, Any],
        source: str,
        initial_ambiguities: List[str],
        initial_questions: List[str],
    ) -> ProposedGoalPlan:
        """Constructs and validates the complete ProposedGoalPlan object graph."""
        raw_gtype = data.get("goal_type", GoalType.SHORT_TERM.value)
        try:
            root_goal_type = GoalType(raw_gtype)
        except ValueError:
            root_goal_type = GoalType.SHORT_TERM

        root_goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        completion_criteria = data.get("completion_criteria", [])
        if not isinstance(completion_criteria, list):
            completion_criteria = [str(completion_criteria)]

        root_goal = Goal(
            goal_id=root_goal_id,
            title=title,
            description=description,
            goal_type=root_goal_type,
            status=GoalStatus.PROPOSED,
            target_date=target_date,
            completion_criteria=[str(c) for c in completion_criteria if str(c).strip()],
            progress=0.0,
            metadata={"source": source, "proposed": True},
        )

        subgoals: List[Goal] = []
        raw_subgoals = data.get("subgoals", [])
        if not isinstance(raw_subgoals, list):
            raw_subgoals = []

        for idx, sg_data in enumerate(raw_subgoals, start=1):
            if not isinstance(sg_data, dict):
                continue
            sg_title = sg_data.get("title", f"Subgoal {idx}").strip()
            if not sg_title:
                sg_title = f"Subgoal {idx}"
            sg_desc = sg_data.get("description", "").strip()
            sg_type_str = sg_data.get("goal_type", GoalType.SHORT_TERM.value)
            try:
                sg_type = GoalType(sg_type_str)
            except ValueError:
                sg_type = GoalType.SHORT_TERM

            sg_criteria = sg_data.get("completion_criteria", [])
            if not isinstance(sg_criteria, list):
                sg_criteria = [str(sg_criteria)]

            sg_id = f"goal_{uuid.uuid4().hex[:8]}"

            # Parse tasks
            sg_tasks: List[GoalTask] = []
            raw_tasks = sg_data.get("tasks", [])
            if isinstance(raw_tasks, list):
                for t_idx, t_data in enumerate(raw_tasks, start=1):
                    if isinstance(t_data, dict):
                        t_desc = t_data.get("description", "").strip()
                        if not t_desc:
                            continue
                        sg_tasks.append(
                            GoalTask(
                                task_id=f"gtask_{uuid.uuid4().hex[:8]}",
                                description=t_desc,
                                completed=False,
                                assigned_skill=t_data.get("assigned_skill"),
                                target_step=t_idx,
                            )
                        )
                    elif isinstance(t_data, str) and t_data.strip():
                        sg_tasks.append(
                            GoalTask(
                                task_id=f"gtask_{uuid.uuid4().hex[:8]}",
                                description=t_data.strip(),
                                completed=False,
                                target_step=t_idx,
                            )
                        )

            subgoal = Goal(
                goal_id=sg_id,
                title=sg_title,
                description=sg_desc,
                goal_type=sg_type,
                status=GoalStatus.PROPOSED,
                parent_goal_id=root_goal_id,
                tasks=sg_tasks,
                target_date=target_date,
                completion_criteria=[str(c) for c in sg_criteria if str(c).strip()],
                progress=0.0,
                metadata={"proposed": True},
            )
            subgoals.append(subgoal)

        # Wire subgoal IDs into root goal
        root_goal.subgoal_ids = [sg.goal_id for sg in subgoals]

        assumptions = data.get("assumptions", [])
        if not isinstance(assumptions, list):
            assumptions = [str(assumptions)]

        ambiguities = list(set(initial_ambiguities + data.get("ambiguities", [])))
        questions = list(set(initial_questions + data.get("clarification_questions", [])))

        return ProposedGoalPlan(
            root_goal=root_goal,
            subgoals=subgoals,
            completion_criteria=root_goal.completion_criteria,
            assumptions=[str(a) for a in assumptions if str(a).strip()],
            ambiguities=ambiguities,
            clarification_questions=questions,
            source=source,
            metadata={"depth": 1, "subgoal_count": len(subgoals)},
        )
