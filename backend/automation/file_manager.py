import logging
import os
import shutil
import glob
from typing import Optional
from .security_proxy import SecurityProxy

logger = logging.getLogger(__name__)


class FileManager:
    """Safe wrapper around filesystem operations with SecurityProxy path validation."""

    def __init__(self, security_proxy: Optional[SecurityProxy] = None):
        self.security = security_proxy or SecurityProxy()

    def create_folder(self, path: str) -> dict:
        is_safe, msg = self.security.validate_safe_path(path, for_destructive=False)
        if not is_safe:
            return {"status": "blocked", "message": msg}
        try:
            os.makedirs(path, exist_ok=True)
            return {"status": "ok", "message": f"Folder created: {path}"}
        except Exception as e:
            logger.error(f"Error creating folder {path}: {e}")
            return {"status": "error", "message": str(e)}

    def list_files(self, path: str) -> dict:
        try:
            if not os.path.isdir(path):
                return {"status": "error", "message": f"Not a directory: {path}"}

            entries = []
            for entry in os.scandir(path):
                info = {
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size_bytes": entry.stat().st_size if entry.is_file() else None
                }
                entries.append(info)
            return {"status": "ok", "path": path, "entries": entries}
        except Exception as e:
            logger.error(f"Error listing {path}: {e}")
            return {"status": "error", "message": str(e)}

    def read_file(self, path: str, max_chars: int = 5000) -> dict:
        try:
            if not os.path.isfile(path):
                return {"status": "error", "message": f"File not found: {path}"}
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            return {"status": "ok", "path": path, "content": content}
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            return {"status": "error", "message": str(e)}

    def rename_file(self, src: str, dest: str) -> dict:
        is_safe_src, msg_src = self.security.validate_safe_path(src, for_destructive=True)
        if not is_safe_src:
            return {"status": "blocked", "message": msg_src}
        is_safe_dst, msg_dst = self.security.validate_safe_path(dest, for_destructive=True)
        if not is_safe_dst:
            return {"status": "blocked", "message": msg_dst}
        try:
            os.rename(src, dest)
            return {"status": "ok", "message": f"Renamed {src} -> {dest}"}
        except Exception as e:
            logger.error(f"Error renaming {src}: {e}")
            return {"status": "error", "message": str(e)}

    def delete_file(self, path: str) -> dict:
        is_safe, msg = self.security.validate_safe_path(path, for_destructive=True)
        if not is_safe:
            return {"status": "blocked", "message": msg}
        try:
            if os.path.isfile(path):
                os.remove(path)
                return {"status": "ok", "message": f"Deleted file: {path}"}
            elif os.path.isdir(path):
                return {"status": "error", "message": "Use delete_folder for directories."}
            else:
                return {"status": "error", "message": f"Path not found: {path}"}
        except Exception as e:
            logger.error(f"Error deleting {path}: {e}")
            return {"status": "error", "message": str(e)}

    def delete_folder(self, path: str) -> dict:
        is_safe, msg = self.security.validate_safe_path(path, for_destructive=True)
        if not is_safe:
            return {"status": "blocked", "message": msg}
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
                return {"status": "ok", "message": f"Deleted folder: {path}"}
            else:
                return {"status": "error", "message": f"Not a directory: {path}"}
        except Exception as e:
            logger.error(f"Error deleting folder {path}: {e}")
            return {"status": "error", "message": str(e)}

    def search_files(self, directory: str, pattern: str) -> dict:
        """Searches for files matching a glob pattern recursively."""
        try:
            matches = glob.glob(os.path.join(directory, "**", pattern), recursive=True)
            return {"status": "ok", "matches": matches[:50]}  # Cap at 50 results
        except Exception as e:
            logger.error(f"Error searching {directory}: {e}")
            return {"status": "error", "message": str(e)}
