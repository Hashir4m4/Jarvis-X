import logging
from typing import Dict, Any, List
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are a senior software architect. Your job is to take a coding task
and break it down into a precise, ordered list of implementation steps.

For each step, output EXACTLY this format:
STEP <n>: <action> | file=<filepath> | description=<what to do>

Where <action> is one of: CREATE, MODIFY, DELETE, TEST, RUN

Example:
STEP 1: CREATE | file=src/utils.py | description=Create a utility module with helper functions
STEP 2: MODIFY | file=src/main.py | description=Import utils and add the main logic
STEP 3: CREATE | file=tests/test_utils.py | description=Write unit tests for the utility module
STEP 4: RUN | file=tests/test_utils.py | description=Run the tests with pytest

Do NOT include explanatory text before or after the steps. Only output STEP lines.
"""


class Planner:
    """Decomposes a high-level coding task into ordered steps."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def plan(self, task: str, repo_context: str = "") -> List[Dict[str, str]]:
        """
        Given a coding task and optional repo context, returns a list of steps.
        Each step has: step_num, action, file, description.
        """
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        ]

        if repo_context:
            messages.append({
                "role": "user",
                "content": f"Repository structure:\n{repo_context}\n\nTask: {task}"
            })
        else:
            messages.append({"role": "user", "content": f"Task: {task}"})

        response = self.llm.chat_sync(messages)
        return self._parse_steps(response)

    def _parse_steps(self, response: str) -> List[Dict[str, str]]:
        """Parses STEP lines from the LLM response."""
        steps = []
        for line in response.split("\n"):
            line = line.strip()
            if not line.upper().startswith("STEP"):
                continue

            try:
                # Remove "STEP N:" prefix
                _, rest = line.split(":", 1)
                parts = [p.strip() for p in rest.split("|")]

                action = parts[0].strip().upper()
                file_path = ""
                description = ""

                for part in parts[1:]:
                    if part.lower().startswith("file="):
                        file_path = part.split("=", 1)[1].strip()
                    elif part.lower().startswith("description="):
                        description = part.split("=", 1)[1].strip()

                steps.append({
                    "step_num": len(steps) + 1,
                    "action": action,
                    "file": file_path,
                    "description": description,
                })
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse step: {line} — {e}")
                continue

        return steps
