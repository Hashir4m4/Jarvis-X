import logging
from typing import Dict, List
from ..llm_client import LLMClient

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM_PROMPT = """You are a senior code reviewer. Review the code below and provide feedback.

Your review must follow this exact format:

VERDICT: PASS or FAIL

ISSUES:
- <issue 1>
- <issue 2>

SUGGESTIONS:
- <suggestion 1>
- <suggestion 2>

Rules:
1. PASS means the code is production-ready with at most minor style nits.
2. FAIL means there are bugs, security issues, or missing error handling that must be fixed.
3. Be concise. Do not rewrite the code, just describe the issues.
4. If there are no issues, write "ISSUES: None" and "SUGGESTIONS: None".
"""


class Reviewer:
    """Reviews generated code for quality, bugs, and security."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def review(self, filepath: str, code: str, task_description: str = "") -> Dict:
        """
        Reviews a piece of code and returns a structured verdict.
        """
        messages = [
            {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"File: {filepath}\n"
                    f"Task: {task_description}\n\n"
                    f"Code:\n```\n{code}\n```"
                )
            },
        ]

        response = self.llm.chat_sync(messages)
        return self._parse_review(response)

    def _parse_review(self, response: str) -> Dict:
        """Parses the review response into a structured dict."""
        result = {
            "verdict": "UNKNOWN",
            "issues": [],
            "suggestions": [],
            "raw": response,
        }

        lines = response.split("\n")
        current_section = None

        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()

            if upper.startswith("VERDICT:"):
                verdict_text = stripped.split(":", 1)[1].strip().upper()
                result["verdict"] = "PASS" if "PASS" in verdict_text else "FAIL"
            elif upper.startswith("ISSUES:"):
                current_section = "issues"
                # Check for inline "None"
                rest = stripped.split(":", 1)[1].strip()
                if rest.lower() == "none":
                    current_section = None
            elif upper.startswith("SUGGESTIONS:"):
                current_section = "suggestions"
                rest = stripped.split(":", 1)[1].strip()
                if rest.lower() == "none":
                    current_section = None
            elif stripped.startswith("- ") and current_section:
                result[current_section].append(stripped[2:].strip())

        return result
