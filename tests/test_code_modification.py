"""
Unit and integration tests for Prompt 62 — Autonomous Code Modification Subsystem.
Tests diff generation, syntax pre-validation, authorization enforcement, path traversal protection,
protected file restrictions, and atomic rollback guarantees.
"""

import os
import tempfile
import pytest
from backend.code_modification.models import PatchStatus, CodePatchProposal
from backend.code_modification.engine import CodeModificationEngine


class MockSecurityProxy:
    def __init__(self, allow_all: bool = True):
        self.allow_all = allow_all
        self.calls = []

    def request_confirmation(self, action_name: str, details: str) -> bool:
        self.calls.append((action_name, details))
        return self.allow_all


def test_syntax_validation_and_diff_generation():
    engine = CodeModificationEngine()
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write("def greeting():\n    return 'Hello'\n")
        tmp_path = f.name

    try:
        # 1. Propose valid syntax change
        new_valid = "def greeting():\n    return 'Hello, World!'\n"
        prop = engine.propose_patch(
            file_path=tmp_path,
            new_content=new_valid,
            rationale="Update greeting output",
        )
        assert prop.syntax_valid is True
        assert "-    return 'Hello'" in prop.diff_unified
        assert "+    return 'Hello, World!'" in prop.diff_unified

        # 2. Propose invalid syntax change
        new_invalid = "def broken(:\n    return 42\n"
        prop_bad = engine.propose_patch(
            file_path=tmp_path,
            new_content=new_invalid,
            rationale="Broken syntax test",
        )
        assert prop_bad.syntax_valid is False
        assert len(prop_bad.validation_errors) == 1

        # Attempting to approve bad syntax must raise error
        with pytest.raises(ValueError, match="syntax validation errors"):
            engine.approve_patch(prop_bad.proposal_id)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_authorization_enforcement_and_rollback():
    security = MockSecurityProxy(allow_all=True)
    engine = CodeModificationEngine(security_proxy=security)

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        f.write("VALUE = 100\n")
        tmp_path = f.name

    try:
        prop = engine.propose_patch(
            file_path=tmp_path,
            new_content="VALUE = 200\n",
            rationale="Update configuration constant",
        )

        # Applying unapproved patch must raise PermissionError
        with pytest.raises(PermissionError, match="requires 'APPROVED'"):
            engine.apply_patch(prop.proposal_id)

        # Authorize patch
        approved = engine.approve_patch(prop.proposal_id, approver="DevLead")
        assert approved is True
        assert prop.status == PatchStatus.APPROVED
        assert len(security.calls) == 1

        # Apply patch
        applied = engine.apply_patch(prop.proposal_id)
        assert applied is True
        assert prop.status == PatchStatus.APPLIED

        with open(tmp_path, "r") as f:
            assert f.read() == "VALUE = 200\n"

        # Rollback patch
        rolled_back = engine.rollback_patch(prop.proposal_id)
        assert rolled_back is True
        assert prop.status == PatchStatus.ROLLED_BACK

        # Verify exact restoration of original state
        with open(tmp_path, "r") as f:
            assert f.read() == "VALUE = 100\n"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_protected_file_and_traversal_restrictions():
    engine = CodeModificationEngine()

    # Path traversal attempt
    with pytest.raises(ValueError, match="Path traversal detected"):
        engine.propose_patch(
            file_path="src/../../etc/passwd",
            new_content="root:x:0:0::",
            rationale="Traversal test",
        )

    # Protected security file attempt
    with pytest.raises(PermissionError, match="protected file/path"):
        engine.propose_patch(
            file_path="C:/Data/Projects/Jarvis X/backend/automation/security_proxy.py",
            new_content="# Bypass",
            rationale="Tamper test",
        )
