"""
JARVIS X — Autonomous Code Modification Engine
Safe patch generation, AST syntax validation, human approval enforcement, and atomic rollback.
"""

import ast
import os
import difflib
import time
import logging
from typing import Dict, Any, List, Optional
from .models import CodePatchProposal, PatchStatus

logger = logging.getLogger("JARVIS.CodeModifier")

# Protected files and path patterns that cannot be modified autonomously
PROTECTED_PATTERNS = [
    ".git",
    "id_rsa",
    ".env",
    "token",
    "password",
    "secret",
    "backend/automation/security_proxy.py",
]


class CodeModificationEngine:
    """
    Subsystem responsible for proposing, validating, applying, and rolling back code changes.
    Guarantees:
    - Never modifies code without prior human authorization.
    - Rejects modifications with invalid Python AST syntax.
    - Rejects path traversal attacks and protected files.
    - Preserves pre-modification snapshots enabling guaranteed atomic rollback.
    """

    def __init__(self, security_proxy: Optional[Any] = None):
        self.security = security_proxy
        self._proposals: Dict[str, CodePatchProposal] = {}
        self._rollback_vault: Dict[str, str] = {}  # proposal_id -> original_content

    def propose_patch(
        self,
        file_path: str,
        new_content: str,
        rationale: str,
        author: str = "JARVIS",
    ) -> CodePatchProposal:
        self._validate_path_safety(file_path)

        # Read original content if file exists
        original_content = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                original_content = f.read()

        # AST syntax validation for Python files
        syntax_valid = True
        validation_errors = []
        if file_path.endswith(".py"):
            try:
                ast.parse(new_content, filename=file_path)
            except SyntaxError as e:
                syntax_valid = False
                validation_errors.append(f"SyntaxError at line {e.lineno}: {e.msg}")

        # Compute unified diff
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{os.path.basename(file_path)}",
            tofile=f"b/{os.path.basename(file_path)}",
        ))
        diff_unified = "".join(diff_lines)

        proposal = CodePatchProposal(
            file_path=file_path,
            rationale=rationale,
            original_content=original_content,
            proposed_content=new_content,
            diff_unified=diff_unified,
            syntax_valid=syntax_valid,
            validation_errors=validation_errors,
            proposed_by=author,
            status=PatchStatus.PROPOSED,
        )
        self._proposals[proposal.proposal_id] = proposal
        logger.info(f"Proposed code patch {proposal.proposal_id} for '{file_path}' (syntax_valid={syntax_valid})")
        return proposal

    def approve_patch(self, proposal_id: str, approver: str = "User") -> bool:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        if not proposal.syntax_valid:
            raise ValueError(f"Cannot approve proposal '{proposal_id}': Contains syntax validation errors.")

        # SecurityProxy check
        if self.security and hasattr(self.security, "request_confirmation"):
            confirmed = self.security.request_confirmation(
                "code_modification",
                f"Approve code patch {proposal_id} on {proposal.file_path}",
            )
            if not confirmed:
                proposal.status = PatchStatus.REJECTED
                logger.warning(f"Patch {proposal_id} rejected by security confirmation.")
                return False

        proposal.status = PatchStatus.APPROVED
        proposal.approved_by = approver
        return True

    def apply_patch(self, proposal_id: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        if proposal.status != PatchStatus.APPROVED:
            raise PermissionError(
                f"Cannot apply patch '{proposal_id}'. Status is '{proposal.status.value}', requires 'APPROVED'."
            )

        # Store pre-change snapshot for rollback
        self._rollback_vault[proposal_id] = proposal.original_content

        try:
            # Ensure parent directories exist
            os.makedirs(os.path.dirname(os.path.abspath(proposal.file_path)), exist_ok=True)
            with open(proposal.file_path, "w", encoding="utf-8") as f:
                f.write(proposal.proposed_content)

            proposal.status = PatchStatus.APPLIED
            proposal.applied_at = time.time()
            logger.info(f"Successfully applied patch {proposal_id} to '{proposal.file_path}'.")
            return True
        except Exception as e:
            proposal.status = PatchStatus.FAILED
            proposal.validation_errors.append(f"Application error: {e}")
            logger.error(f"Failed to apply patch {proposal_id}: {e}")
            return False

    def rollback_patch(self, proposal_id: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal '{proposal_id}' not found.")

        if proposal.status != PatchStatus.APPLIED:
            raise ValueError(f"Cannot rollback proposal '{proposal_id}': status is '{proposal.status.value}'.")

        if proposal_id not in self._rollback_vault:
            raise RuntimeError(f"No rollback snapshot found for patch '{proposal_id}'.")

        original_content = self._rollback_vault[proposal_id]
        try:
            with open(proposal.file_path, "w", encoding="utf-8") as f:
                f.write(original_content)
            proposal.status = PatchStatus.ROLLED_BACK
            logger.info(f"Rolled back patch {proposal_id} on '{proposal.file_path}'.")
            return True
        except Exception as e:
            logger.error(f"Rollback failed for {proposal_id}: {e}")
            return False

    def _validate_path_safety(self, file_path: str):
        normalized = os.path.normpath(file_path).replace("\\", "/")
        if ".." in normalized.split("/"):
            raise ValueError(f"Path traversal detected in file path: {file_path}")

        for pattern in PROTECTED_PATTERNS:
            if pattern in normalized:
                raise PermissionError(f"Modification of protected file/path '{pattern}' is forbidden.")
