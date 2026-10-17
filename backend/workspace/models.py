"""
Contextual Workspace Intelligence Models.
Prompt 73 — Contextual Workspace Intelligence.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time
import os


@dataclass
class WorkspaceFileMetadata:
    rel_path: str
    abs_path: str
    size_bytes: int
    modified_time: float
    content_hash: str
    file_type: str = "text"
    summary: Optional[str] = None
    is_sensitive: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rel_path": self.rel_path,
            "abs_path": self.abs_path,
            "size_bytes": self.size_bytes,
            "modified_time": self.modified_time,
            "content_hash": self.content_hash,
            "file_type": self.file_type,
            "summary": self.summary,
            "is_sensitive": self.is_sensitive
        }


@dataclass
class WorkspaceConfig:
    workspace_id: str
    root_path: str
    authorized_subdirectories: List[str] = field(default_factory=list)
    excluded_patterns: List[str] = field(default_factory=lambda: [
        r"\.git", r"\.venv", r"node_modules", r"\.env", r"\.pem$", r"\.key$", r"id_rsa"
    ])
    max_file_size_bytes: int = 1024 * 1024  # 1 MB
    allow_indexing: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "root_path": self.root_path,
            "authorized_subdirectories": list(self.authorized_subdirectories),
            "excluded_patterns": list(self.excluded_patterns),
            "max_file_size_bytes": self.max_file_size_bytes,
            "allow_indexing": self.allow_indexing
        }


@dataclass
class WorkspaceContextReport:
    workspace_id: str
    total_files_indexed: int
    indexed_files: List[WorkspaceFileMetadata] = field(default_factory=list)
    recent_relevant_files: List[str] = field(default_factory=list)
    last_indexed_time: float = field(default_factory=time.time)
    active_project: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "total_files_indexed": self.total_files_indexed,
            "indexed_files": [f.to_dict() for f in self.indexed_files],
            "recent_relevant_files": list(self.recent_relevant_files),
            "last_indexed_time": self.last_indexed_time,
            "active_project": self.active_project
        }
