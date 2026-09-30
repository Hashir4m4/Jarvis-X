import os
import re
import datetime
import logging
from typing import Dict, Any, List, Optional, Union

try:
    import yaml
    _YAML = True
except ImportError:
    _YAML = False

logger = logging.getLogger("JARVIS.VaultManager")


class VaultManager:
    """
    Obsidian-compatible Markdown Vault Manager for JARVIS OS.
    Seamlessly manages human-readable knowledge, structured daily notes,
    reports, raw captures, wiki knowledge, backlinks, and tags.
    Independent of Obsidian runtime with strict path traversal prevention.
    """

    def __init__(self, vault_root: Optional[str] = None):
        if vault_root is None:
            # Default to workspace root vault directory
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            vault_root = os.path.join(base_dir, "vault")

        self.vault_root = os.path.realpath(os.path.abspath(vault_root))
        self.raw_dir = os.path.join(self.vault_root, "raw")
        self.wiki_dir = os.path.join(self.vault_root, "wiki")
        self.outputs_dir = os.path.join(self.vault_root, "outputs")
        self.daily_dir = os.path.join(self.vault_root, "daily")

        self._ensure_directories()

    def _ensure_directories(self):
        """Ensures all standard Obsidian vault subfolders exist."""
        for d in [self.vault_root, self.raw_dir, self.wiki_dir, self.outputs_dir, self.daily_dir]:
            os.makedirs(d, exist_ok=True)

    # ─────────────────────────────────────────────────────────────
    # Safe Path Resolution & Traversal Prevention
    # ─────────────────────────────────────────────────────────────

    def _safe_resolve_path(self, target_path: str, base_folder: Optional[str] = None) -> str:
        """
        Safely resolves a file path within the vault root.
        Guards against directory traversal (e.g. '../', '..\\', absolute outside paths).
        """
        if base_folder:
            # If base_folder provided, resolve relative to that vault subfolder
            target = os.path.join(self.vault_root, base_folder, target_path)
        elif os.path.isabs(target_path):
            target = target_path
        else:
            target = os.path.join(self.vault_root, target_path)

        resolved = os.path.realpath(os.path.abspath(target))

        # Check that resolved path is strictly inside vault_root
        common = os.path.commonpath([self.vault_root, resolved])
        if common != self.vault_root:
            raise ValueError(f"Security Violation: Path traversal detected outside vault root ({target_path})")

        return resolved

    @staticmethod
    def _slugify(text: str) -> str:
        """Converts titles into clean, filesystem-safe filenames."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "_", text)
        return text or "untitled"

    # ─────────────────────────────────────────────────────────────
    # Frontmatter Parsing & Formatting
    # ─────────────────────────────────────────────────────────────

    def _format_frontmatter(self, metadata: Dict[str, Any]) -> str:
        """Formats metadata dictionary into YAML frontmatter string."""
        if not metadata:
            return ""
        if _YAML:
            try:
                dumped = yaml.safe_dump(metadata, sort_keys=False).strip()
                return f"---\n{dumped}\n---\n\n"
            except Exception as e:
                logger.warning(f"PyYAML formatting failed: {e}. Using fallback.")

        # Fallback YAML formatter
        lines = ["---"]
        for k, v in metadata.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        lines.append("---\n\n")
        return "\n".join(lines)

    def _parse_frontmatter(self, content: str) -> (Dict[str, Any], str):
        """Extracts YAML frontmatter and markdown body from note content."""
        pattern = r"^---\s*\n(.*?)\n---\s*\n?(.*)$"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return {}, content

        raw_yaml = match.group(1)
        body = match.group(2)

        metadata = {}
        if _YAML:
            try:
                metadata = yaml.safe_load(raw_yaml) or {}
            except Exception:
                pass

        if not metadata:
            # Fallback simple parser
            for line in raw_yaml.splitlines():
                if ":" in line and not line.strip().startswith("-"):
                    parts = line.split(":", 1)
                    metadata[parts[0].strip()] = parts[1].strip()

        return metadata, body

    # ─────────────────────────────────────────────────────────────
    # 1. Daily Notes (vault/daily/YYYY-MM-DD.md)
    # ─────────────────────────────────────────────────────────────

    def create_daily_note(
        self,
        content: Optional[str] = None,
        date_str: Optional[str] = None,
        priorities: Optional[List[str]] = None,
        activity: Optional[List[str]] = None,
        reports: Optional[List[str]] = None,
        decisions: Optional[List[str]] = None,
        reflection: Optional[str] = None,
        tomorrow: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Creates or updates a structured Obsidian Daily Note in vault/daily/YYYY-MM-DD.md.
        Contains standard headings:
          # Daily Log
          ## Priorities
          ## Activity
          ## Reports
          ## Decisions
          ## Reflection
          ## Tomorrow
        """
        if not date_str:
            date_str = datetime.date.today().isoformat()

        file_path = self._safe_resolve_path(f"{date_str}.md", base_folder="daily")
        timestamp_str = datetime.datetime.now().strftime("%H:%M:%S")

        # Build sections
        prio_text = "\n".join(f"- {p}" for p in priorities) if priorities else "- [ ] No priorities set."
        act_text = "\n".join(f"- {a}" for a in activity) if activity else f"- [{timestamp_str}] Daily log initialized."
        rep_text = "\n".join(f"- {r}" for r in reports) if reports else "- None."
        dec_text = "\n".join(f"- {d}" for d in decisions) if decisions else "- Standard operational guidelines."
        ref_text = reflection or "- System executing nominal parameters."
        tom_text = "\n".join(f"- {t}" for t in tomorrow) if tomorrow else "- [ ] Morning intelligence review."

        if os.path.exists(file_path):
            # If file exists, append content or update log section
            with open(file_path, "a", encoding="utf-8") as f:
                if content:
                    f.write(f"\n\n### [{timestamp_str}] Update\n{content.strip()}\n")
                if activity:
                    f.write("\n### New Activity\n" + act_text + "\n")
        else:
            frontmatter = {
                "type": "daily_note",
                "date": date_str,
                "source": "jarvis",
                "tags": tags or ["daily", "jarvis_log"]
            }
            body = (
                f"# Daily Log — {date_str}\n\n"
                f"## Priorities\n{prio_text}\n\n"
                f"## Activity\n{act_text}\n\n"
                f"## Reports\n{rep_text}\n\n"
                f"## Decisions\n{dec_text}\n\n"
                f"## Reflection\n{ref_text}\n\n"
                f"## Tomorrow\n{tom_text}\n"
            )
            if content:
                body += f"\n## Notes\n{content.strip()}\n"

            full_content = self._format_frontmatter(frontmatter) + body
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_content)

        logger.info(f"Obsidian daily note synced: {file_path}")
        return file_path

    # ─────────────────────────────────────────────────────────────
    # 2. Reports (vault/outputs/<slug>.md)
    # ─────────────────────────────────────────────────────────────

    def create_report(
        self,
        title: str,
        content: str,
        report_type: str = "report",
        tags: Optional[List[str]] = None,
        backlinks: Optional[List[str]] = None
    ) -> str:
        """
        Creates a structured report markdown document in vault/outputs/<slug>.md.
        """
        slug = self._slugify(title)
        file_path = self._safe_resolve_path(f"{slug}.md", base_folder="outputs")
        date_str = datetime.date.today().isoformat()

        frontmatter = {
            "title": title,
            "type": report_type,
            "date": date_str,
            "source": "jarvis",
            "tags": tags or ["report", "jarvis_output"]
        }

        body = f"# {title}\n\n{content.strip()}\n"
        if backlinks:
            body += "\n\n## Related Notes\n" + "\n".join(f"- [[{b}]]" for b in backlinks) + "\n"

        full_doc = self._format_frontmatter(frontmatter) + body

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_doc)

        logger.info(f"Obsidian report generated: {file_path}")
        return file_path

    # ─────────────────────────────────────────────────────────────
    # 3. Raw Captures (vault/raw/<slug>.md)
    # ─────────────────────────────────────────────────────────────

    def raw_capture(
        self,
        title: str,
        content: str,
        source: str = "user_capture",
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Saves raw thoughts, quick notes, and snippets in vault/raw/<slug>.md.
        """
        slug = self._slugify(title)
        file_path = self._safe_resolve_path(f"{slug}.md", base_folder="raw")
        date_str = datetime.date.today().isoformat()

        frontmatter = {
            "title": title,
            "type": "raw_capture",
            "date": date_str,
            "source": source,
            "tags": tags or ["raw", "capture"]
        }

        full_doc = self._format_frontmatter(frontmatter) + f"# {title}\n\n{content.strip()}\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_doc)

        logger.info(f"Raw capture stored: {file_path}")
        return file_path

    # ─────────────────────────────────────────────────────────────
    # 4. Wiki Knowledge (vault/wiki/<slug>.md)
    # ─────────────────────────────────────────────────────────────

    def create_wiki_note(
        self,
        title: str,
        content: str,
        backlinks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Saves curated evergreen wiki knowledge in vault/wiki/<slug>.md.
        """
        slug = self._slugify(title)
        file_path = self._safe_resolve_path(f"{slug}.md", base_folder="wiki")
        date_str = datetime.date.today().isoformat()

        frontmatter = {
            "title": title,
            "type": "wiki_article",
            "date": date_str,
            "source": "jarvis",
            "tags": tags or ["wiki", "knowledge"]
        }

        body = f"# {title}\n\n{content.strip()}\n"
        if backlinks:
            body += "\n\n## Linked Concepts\n" + "\n".join(f"- [[{b}]]" for b in backlinks) + "\n"

        full_doc = self._format_frontmatter(frontmatter) + body

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_doc)

        logger.info(f"Wiki note stored: {file_path}")
        return file_path

    # ─────────────────────────────────────────────────────────────
    # Generic Read / Write / Update Operations
    # ─────────────────────────────────────────────────────────────

    def write_note(
        self,
        folder: str,
        filename: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Writes a note to a designated vault subfolder (raw, wiki, outputs, daily).
        Guards against directory traversal.
        """
        if not filename.endswith(".md"):
            filename = f"{filename}.md"

        file_path = self._safe_resolve_path(filename, base_folder=folder)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if metadata:
            full_content = self._format_frontmatter(metadata) + content
        else:
            full_content = content

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        return file_path

    def read_note(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Reads a markdown note from disk, extracting frontmatter, body, and Obsidian [[wiki-links]].
        Guards against directory traversal.
        """
        try:
            resolved = self._safe_resolve_path(file_path)
        except ValueError:
            return None

        if not os.path.isfile(resolved):
            return None

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            raw_content = f.read()

        metadata, body = self._parse_frontmatter(raw_content)
        links = re.findall(r"\[\[(.*?)\]\]", raw_content)

        return {
            "path": resolved,
            "filename": os.path.basename(resolved),
            "frontmatter": metadata,
            "body": body,
            "raw": raw_content,
            "links": links
        }

    def update_note(
        self,
        file_path: str,
        new_content: str,
        metadata_updates: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Updates an existing note's body or frontmatter metadata.
        Guards against directory traversal.
        """
        try:
            resolved = self._safe_resolve_path(file_path)
        except ValueError:
            return False

        if not os.path.isfile(resolved):
            return False

        existing = self.read_note(resolved)
        if not existing:
            return False

        meta = existing["frontmatter"]
        if metadata_updates:
            meta.update(metadata_updates)

        full_content = self._format_frontmatter(meta) + new_content.strip() + "\n"

        with open(resolved, "w", encoding="utf-8") as f:
            f.write(full_content)

        return True

    def link_notes(
        self,
        source_path: str,
        target_name: str,
        link_text: Optional[str] = None
    ) -> bool:
        """
        Adds an Obsidian-compatible [[Target Note|Link Text]] wiki-link to the source note.
        """
        try:
            resolved = self._safe_resolve_path(source_path)
        except ValueError:
            return False

        if not os.path.isfile(resolved):
            return False

        link_target = f"[[{target_name}|{link_text}]]" if link_text else f"[[{target_name}]]"

        with open(resolved, "a", encoding="utf-8") as f:
            f.write(f"\n\n## Related Notes\n- {link_target}\n")

        return True

    # ─────────────────────────────────────────────────────────────
    # Backlinks, Tags & Search
    # ─────────────────────────────────────────────────────────────

    def get_backlinks(self, target_name: str) -> List[Dict[str, Any]]:
        """
        Finds all notes in the vault that link to `target_name` via [[target_name]].
        """
        clean_target = target_name.replace(".md", "").lower()
        backlinks = []

        for root, _, files in os.walk(self.vault_root):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    note = self.read_note(full_path)
                    if not note:
                        continue

                    # Check if any link targets clean_target
                    for link in note.get("links", []):
                        link_clean = link.split("|")[0].strip().lower()
                        if link_clean == clean_target:
                            backlinks.append({
                                "source_path": full_path,
                                "source_filename": file,
                                "link": link
                            })
                            break
        return backlinks

    def get_all_tags(self) -> List[str]:
        """
        Extracts all frontmatter and inline #tags across all markdown notes in the vault.
        """
        tags_set = set()
        for root, _, files in os.walk(self.vault_root):
            for file in files:
                if file.endswith(".md"):
                    note = self.read_note(os.path.join(root, file))
                    if not note:
                        continue

                    # 1. Frontmatter tags
                    fm_tags = note["frontmatter"].get("tags", [])
                    if isinstance(fm_tags, list):
                        for t in fm_tags:
                            tags_set.add(str(t).lstrip("#"))
                    elif isinstance(fm_tags, str):
                        tags_set.add(fm_tags.lstrip("#"))

                    # 2. Inline #tags
                    inline_tags = re.findall(r"(?:^|\s)#([a-zA-Z0-9_\-]+)", note["raw"])
                    for t in inline_tags:
                        tags_set.add(t)

        return sorted(list(tags_set))

    def search_notes(
        self,
        query: str,
        folder: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Full-text keyword, tag, and link search across markdown notes in the vault.
        """
        try:
            search_dir = self._safe_resolve_path(folder) if folder else self.vault_root
        except ValueError:
            return []

        if not os.path.exists(search_dir):
            return []

        query_lower = query.lower()
        results = []

        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    note = self.read_note(full_path)
                    if not note:
                        continue

                    raw_text = note["raw"].lower()
                    if query_lower in raw_text or query_lower in file.lower():
                        score = raw_text.count(query_lower) + (5 if query_lower in file.lower() else 0)
                        results.append({
                            "path": full_path,
                            "filename": file,
                            "folder": os.path.relpath(root, self.vault_root),
                            "frontmatter": note["frontmatter"],
                            "snippet": note["body"][:200].strip(),
                            "score": score
                        })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def list_notes(self, folder: Optional[str] = None) -> List[str]:
        """Lists all markdown files in the vault or a subfolder."""
        try:
            search_dir = self._safe_resolve_path(folder) if folder else self.vault_root
        except ValueError:
            return []

        notes = []
        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.endswith(".md"):
                    notes.append(os.path.relpath(os.path.join(root, file), self.vault_root))
        return notes
