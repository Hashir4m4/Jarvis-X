"""
Contextual Workspace Intelligence Service.
Prompt 73 — Contextual Workspace Intelligence.
"""
import logging
import os
import re
import hashlib
import time
from typing import Dict, Any, List, Optional

from backend.workspace.models import (
    WorkspaceFileMetadata, WorkspaceConfig, WorkspaceContextReport
)

logger = logging.getLogger("JARVIS.WorkspaceIntelligence")


class WorkspaceIntelligenceService:
    """
    Workspace-Aware Intelligence Engine.
    Safety Guarantees:
    - Strictly confines indexing to authorized workspace root directories.
    - Path traversal attacks (e.g. `../../etc/passwd`) are rejected.
    - Excludes secrets, credentials, environment files, and large binary blobs.
    - Treats file content strictly as untrusted data, mitigating prompt injection.
    """

    def __init__(self, config: Optional[WorkspaceConfig] = None, memory_api: Optional[Any] = None):
        self.config = config
        self.memory = memory_api
        self._index: Dict[str, WorkspaceFileMetadata] = {}
        self._last_indexed_time: float = 0.0

    def configure_workspace(self, root_path: str, workspace_id: str = "default_ws") -> WorkspaceConfig:
        norm_path = os.path.abspath(root_path)
        self.config = WorkspaceConfig(workspace_id=workspace_id, root_path=norm_path)
        return self.config

    def _is_path_safe(self, target_path: str) -> bool:
        if not self.config:
            return False
        abs_target = os.path.abspath(target_path)
        abs_root = os.path.abspath(self.config.root_path)
        # Check that target is within or equal to root
        return os.path.commonpath([abs_root, abs_target]) == abs_root

    def _is_excluded(self, file_path: str) -> bool:
        if not self.config:
            return True
        for pattern in self.config.excluded_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
        return False

    def scan_and_index(self) -> WorkspaceContextReport:
        if not self.config or not os.path.isdir(self.config.root_path):
            return WorkspaceContextReport(
                workspace_id=self.config.workspace_id if self.config else "none",
                total_files_indexed=0
            )

        indexed: List[WorkspaceFileMetadata] = []
        recent_files: List[str] = []
        root = self.config.root_path

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune excluded directories in-place
            dirnames[:] = [d for d in dirnames if not self._is_excluded(d)]

            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(full_path, root)

                if self._is_excluded(full_path) or self._is_excluded(rel_path):
                    continue

                try:
                    stat = os.stat(full_path)
                    if stat.st_size > self.config.max_file_size_bytes:
                        continue

                    # Compute content hash
                    hasher = hashlib.sha256()
                    with open(full_path, "rb") as f:
                        buf = f.read(4096)
                        while buf:
                            hasher.update(buf)
                            buf = f.read(4096)
                    h = hasher.hexdigest()[:16]

                    meta = WorkspaceFileMetadata(
                        rel_path=rel_path.replace("\\", "/"),
                        abs_path=full_path,
                        size_bytes=stat.st_size,
                        modified_time=stat.st_mtime,
                        content_hash=h,
                        file_type=os.path.splitext(fname)[1].lstrip(".") or "txt"
                    )
                    self._index[meta.rel_path] = meta
                    indexed.append(meta)
                    recent_files.append(meta.rel_path)
                except Exception as e:
                    logger.debug(f"Skipping file {full_path}: {e}")

        # Sort recent files by modified time
        indexed.sort(key=lambda m: m.modified_time, reverse=True)
        recent_files = [m.rel_path for m in indexed[:10]]
        self._last_indexed_time = time.time()

        return WorkspaceContextReport(
            workspace_id=self.config.workspace_id,
            total_files_indexed=len(indexed),
            indexed_files=indexed,
            recent_relevant_files=recent_files,
            last_indexed_time=self._last_indexed_time,
            active_project=os.path.basename(root)
        )

    def search_context(self, query: str, max_results: int = 5) -> List[WorkspaceFileMetadata]:
        """Performs simple contextual search over indexed file paths and metadata."""
        q_lower = query.lower()
        matches = []
        for meta in self._index.values():
            if q_lower in meta.rel_path.lower():
                matches.append(meta)
            elif meta.summary and q_lower in meta.summary.lower():
                matches.append(meta)
        return matches[:max_results]

    def read_workspace_file_safe(self, rel_path: str) -> Optional[str]:
        """Safely reads a workspace file with path traversal check."""
        if not self.config:
            return None
        full_path = os.path.join(self.config.root_path, rel_path)
        if not self._is_path_safe(full_path) or self._is_excluded(full_path):
            logger.warning(f"Blocked unauthorized file access: {full_path}")
            return None

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read(self.config.max_file_size_bytes)
        except Exception as e:
            logger.error(f"Failed to read file {full_path}: {e}")
            return None
