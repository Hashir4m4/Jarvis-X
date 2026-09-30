import os
import logging
import subprocess
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Language detection by file extension
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "cpp",
    ".hpp": "cpp",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".ps1": "powershell",
    ".bat": "batch",
    ".sql": "sql",
}

# Directories to skip when scanning repos
IGNORED_DIRS = {
    "__pycache__", ".git", "node_modules", ".venv", "venv", "env",
    ".idea", ".vscode", "dist", "build", ".next", ".cache",
    "target", "bin", "obj", ".tox", ".mypy_cache", ".pytest_cache",
}

IGNORED_FILES = {
    ".DS_Store", "Thumbs.db", ".gitignore",
}


def detect_language(filepath: str) -> str:
    """Detects the programming language from a file extension."""
    _, ext = os.path.splitext(filepath)
    return LANGUAGE_MAP.get(ext.lower(), "unknown")


def read_file_content(filepath: str, max_chars: int = 10000) -> Optional[str]:
    """Reads a file's content with a size cap."""
    try:
        if not os.path.isfile(filepath):
            return None
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_chars)
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return None


def write_file_content(filepath: str, content: str) -> Dict:
    """Writes content to a file, creating parent dirs if needed."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "ok", "path": filepath}
    except Exception as e:
        logger.error(f"Error writing {filepath}: {e}")
        return {"status": "error", "message": str(e)}


def scan_repository(repo_path: str, max_files: int = 200) -> List[Dict]:
    """
    Scans a repository and returns a list of files with metadata.
    Skips common non-source directories.
    """
    files = []
    try:
        for root, dirs, filenames in os.walk(repo_path):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            for fname in filenames:
                if fname in IGNORED_FILES:
                    continue
                filepath = os.path.join(root, fname)
                rel_path = os.path.relpath(filepath, repo_path)
                lang = detect_language(filepath)
                try:
                    size = os.path.getsize(filepath)
                except OSError:
                    size = 0

                files.append({
                    "path": rel_path,
                    "language": lang,
                    "size_bytes": size,
                })

                if len(files) >= max_files:
                    return files
    except Exception as e:
        logger.error(f"Error scanning repo {repo_path}: {e}")
    return files


def build_repo_tree(repo_path: str, max_depth: int = 4) -> str:
    """Builds a tree-style string representation of a repo structure."""
    lines = []

    def _walk(path, prefix, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in IGNORED_DIRS]
        files = [e for e in entries if e.is_file() and e.name not in IGNORED_FILES]

        items = dirs + files
        for i, entry in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "--- " if is_last else "|-- "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if is_last else "|   "
                _walk(entry.path, prefix + extension, depth + 1)

    lines.append(os.path.basename(repo_path) + "/")
    _walk(repo_path, "", 1)
    return "\n".join(lines)


def extract_imports(filepath: str) -> List[str]:
    """Extracts import statements from a Python file."""
    content = read_file_content(filepath, max_chars=50000)
    if not content:
        return []
    imports = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            imports.append(stripped)
    return imports


def analyze_dependencies(repo_path: str) -> Dict:
    """Detects dependency files in a repo and returns their contents."""
    dep_files = {
        "requirements.txt": None,
        "setup.py": None,
        "setup.cfg": None,
        "pyproject.toml": None,
        "package.json": None,
        "Cargo.toml": None,
        "go.mod": None,
        "pom.xml": None,
        "build.gradle": None,
    }

    found = {}
    for dep_file in dep_files:
        full_path = os.path.join(repo_path, dep_file)
        if os.path.isfile(full_path):
            content = read_file_content(full_path, max_chars=5000)
            found[dep_file] = content

    return found


# ── Git Integration ──────────────────────────────────────────────

def git_status(repo_path: str) -> str:
    """Returns `git status` output."""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except Exception as e:
        return f"Error: {e}"


def git_diff(repo_path: str) -> str:
    """Returns `git diff` output."""
    try:
        result = subprocess.run(
            ["git", "diff"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()[:5000]
    except Exception as e:
        return f"Error: {e}"


def git_log(repo_path: str, n: int = 10) -> str:
    """Returns recent git log entries."""
    try:
        result = subprocess.run(
            ["git", "log", f"-{n}", "--oneline"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"


def git_commit(repo_path: str, message: str) -> str:
    """Stages all changes and commits."""
    try:
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, timeout=10)
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except Exception as e:
        return f"Error: {e}"
