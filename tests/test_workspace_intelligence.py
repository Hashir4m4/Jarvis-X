"""
Unit and Integration Tests for Prompt 73 — Contextual Workspace Intelligence.
"""
import pytest
import os
import tempfile
from backend.workspace.models import WorkspaceConfig, WorkspaceFileMetadata, WorkspaceContextReport
from backend.workspace.service import WorkspaceIntelligenceService


def test_workspace_intelligence_indexing_and_exclusion():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create normal files
        f1 = os.path.join(tmp_dir, "main.py")
        with open(f1, "w") as f:
            f.write("print('hello world')")

        sub = os.path.join(tmp_dir, "src")
        os.makedirs(sub, exist_ok=True)
        f2 = os.path.join(sub, "utils.py")
        with open(f2, "w") as f:
            f.write("def add(a, b): return a + b")

        # Create sensitive files that must be excluded
        f_env = os.path.join(tmp_dir, ".env")
        with open(f_env, "w") as f:
            f.write("SECRET_KEY=123456")

        service = WorkspaceIntelligenceService()
        service.configure_workspace(tmp_dir, workspace_id="test_ws")

        report = service.scan_and_index()
        assert report.total_files_indexed == 2
        indexed_names = [f.rel_path for f in report.indexed_files]
        assert "main.py" in indexed_names
        assert "src/utils.py" in indexed_names or "src\\utils.py" in [x.replace("/", "\\") for x in indexed_names]
        assert ".env" not in indexed_names


def test_workspace_intelligence_path_traversal_protection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        outside = os.path.join(tmp_dir, "..", "outside.txt")
        service = WorkspaceIntelligenceService()
        service.configure_workspace(tmp_dir, workspace_id="test_ws")

        # Attempt to read path outside workspace
        content = service.read_workspace_file_safe("../../outside.txt")
        assert content is None


def test_workspace_intelligence_search():
    with tempfile.TemporaryDirectory() as tmp_dir:
        f = os.path.join(tmp_dir, "server_api.py")
        with open(f, "w") as fp:
            fp.write("# API server")

        service = WorkspaceIntelligenceService()
        service.configure_workspace(tmp_dir)
        service.scan_and_index()

        results = service.search_context("server")
        assert len(results) == 1
        assert "server_api.py" in results[0].rel_path
