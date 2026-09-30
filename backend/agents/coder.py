import logging
from typing import Dict, Any
from ..llm_client import LLMClient
from . import code_tools

logger = logging.getLogger(__name__)

CODER_SYSTEM_PROMPT = """You are an expert software engineer. You write clean, production-ready code.

Rules:
1. Output ONLY the complete file content. No explanations before or after.
2. Include proper imports, error handling, docstrings, and type hints.
3. Follow the conventions of the language you are writing in.
4. Do NOT use placeholder comments like "# TODO" or "# implement later".
5. Every function must be complete and working.

When modifying an existing file, output the ENTIRE updated file content, not just the changed lines.
"""


class Coder:
    """Generates code for a single step from the Planner."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def generate(self, step: Dict[str, str], existing_content: str = None) -> str:
        """
        Generates code for a given step.
        If existing_content is provided, the LLM will modify it.
        Returns the complete file content as a string.
        """
        messages = [
            {"role": "system", "content": CODER_SYSTEM_PROMPT},
        ]

        prompt = f"Action: {step['action']}\nFile: {step['file']}\nTask: {step['description']}"

        if existing_content:
            prompt += f"\n\nExisting file content:\n```\n{existing_content}\n```\n\nModify this file according to the task. Output the COMPLETE updated file."
        else:
            prompt += "\n\nCreate this file from scratch. Output ONLY the file content."

        messages.append({"role": "user", "content": prompt})

        response = self.llm.chat_sync(messages)
        return self._extract_code(response)

    def _extract_code(self, response: str) -> str:
        """
        Extracts code from the LLM response.
        Handles cases where the LLM wraps the code in markdown code fences.
        """
        lines = response.split("\n")
        code_lines = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith("```") and not in_code_block:
                in_code_block = True
                continue
            elif line.strip() == "```" and in_code_block:
                in_code_block = False
                continue

            if in_code_block:
                code_lines.append(line)

        # If we found code fences, return the extracted code
        if code_lines:
            return "\n".join(code_lines)

        # Otherwise the LLM likely returned raw code without fences
        return response.strip()
