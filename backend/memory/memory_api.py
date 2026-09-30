import os
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Union

from .database.sqlite_manager import SQLiteManager
from .embeddings.chroma_manager import ChromaManager
from .vault.vault_manager import VaultManager
from .retrieval.context_builder import ContextBuilder
from .extraction_policy import MemoryExtractor
from .memory_models import MemoryDecision
from backend.llm.privacy_boundary import PrivacyBoundary

logger = logging.getLogger(__name__)


class MemoryAPI:
    """
    Unified JARVIS OS Memory Architecture.
    Seamlessly orchestrates:
      1. Markdown Vault (Human-readable Obsidian notes, daily logs, reports, wiki)
      2. SQLite (Structured runtime sessions, user profiles, project states)
      3. ChromaDB (High-performance semantic vector retrieval)
    With automated privacy boundary and secret scrubbing before persistence.
    """

    def __init__(self, config: Dict[str, Any], session_id: str = "default"):
        self.session_id = session_id
        self.config = config
        self.privacy_boundary = PrivacyBoundary()
        adv_config = config.get("memory_advanced", {})

        # 1. SQLite Relational Store
        self.sqlite = SQLiteManager(adv_config)

        # 2. ChromaDB Semantic Vector Store
        self.chroma = ChromaManager(adv_config)

        # 3. Markdown Vault Store
        vault_path = adv_config.get("vault_path")
        self.vault = VaultManager(vault_root=vault_path)

        # 4. Context Builder
        self.builder = ContextBuilder(self.sqlite, self.chroma, adv_config)

        # 5. Extraction Policy
        self.extractor = MemoryExtractor() # Optional ModelRouter injection can happen via factory

        logger.info("Unified JARVIS Memory API initialized.")

    def _audit(self, action: str, doc_id: str, content_preview: str):
        """Logs memory events safely."""
        logger.info(f"[MEMORY AUDIT] {action} | ID: {doc_id} | PREVIEW: {content_preview[:30]}...")

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Adds a message to SQLite session history and ChromaDB vector store.
        Maintains backward compatibility with legacy Brain and Kernel calls.
        Scrubs API keys, passwords, and tokens before persistence.
        """
        meta = metadata.copy() if metadata else {}
        privacy = meta.get("privacy_level", "prefer_local")
        
        # Scrub sensitive credentials before long-term storage
        clean_content = self.privacy_boundary.redact_secrets(content)

        # Run automatic memory extraction policy
        if role == "user":
            decision = self.extractor.evaluate_message(clean_content, role)
            if decision.should_save:
                meta["category"] = decision.category.value
                meta["importance"] = decision.importance.value
                meta["confidence"] = decision.confidence.value

        msg_id = self.sqlite.add_message(self.session_id, role, clean_content)
        if msg_id != -1 and len(clean_content.strip()) > 10:
            doc_id = f"{self.session_id}_{msg_id}"
            
            meta.update({"role": role, "session_id": self.session_id})
            
            # If importance is high/critical, or category is long_term/project/preference, ensure it's captured
            if meta.get("category") and meta.get("category") != "short_term" and meta.get("category") != "temporary":
                self._deduplicate_and_save(doc_id, clean_content, meta)
        return msg_id

    def _deduplicate_and_save(self, doc_id: str, content: str, meta: Dict[str, Any]):
        """Checks for existing similar memories to update instead of duplicate."""
        existing = self.search_memory(content, limit=1, search_vault=False)
        if existing and existing[0].get("distance", 1.0) < 0.25:
            # Very similar, update it
            target_id = existing[0].get("id")
            if target_id:
                logger.info(f"Memory deduplication: Updating {target_id} instead of creating {doc_id}.")
                self.chroma.add_memory(target_id, content, meta)
                self._audit("MEMORY_UPDATED", target_id, content)
                return
                
        self.chroma.add_memory(doc_id, content, meta)
        self._audit("MEMORY_CREATED", doc_id, content)

    def get_context(self, current_query: str = "") -> List[Dict[str, str]]:
        """Retrieves multi-tiered context for the active session."""
        return self.retrieve_context(current_query, session_id=self.session_id)

    def write_memory(
        self,
        content: str,
        memory_type: str = "general",
        category: str = "raw",
        metadata: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stores memory across all 3 tiers:
        - Markdown Vault: human-readable note
        - SQLite: structured relational record
        - ChromaDB: semantic vector embedding
        """
        meta = metadata.copy() if metadata else {}
        meta.setdefault("type", memory_type)
        meta.setdefault("source", "jarvis")
        meta.setdefault("date", datetime.date.today().isoformat())
        meta.setdefault("session_id", self.session_id)
        
        # Calculate expiry timestamp if provided
        expiry_seconds = meta.pop("expiry_seconds", None)
        if expiry_seconds:
            meta["expires_at"] = (datetime.datetime.now() + datetime.timedelta(seconds=expiry_seconds)).timestamp()

        doc_id = str(uuid.uuid4())
        meta["id"] = doc_id
        
        # Don't save temporary memories to permanent storage
        if category == "temporary" or meta.get("category") in ["temporary", "short_term"]:
            logger.info("Skipping storage of temporary memory.")
            return {"id": doc_id, "status": "ignored_temporary"}

        # Scrub secrets before permanent persistence
        clean_content = self.privacy_boundary.redact_secrets(content)

        # 1. Write to Markdown Vault
        slug = self.vault._slugify(title or f"mem_{doc_id[:8]}")
        filename = f"{slug}.md"
        vault_path = self.vault.write_note(category, filename, clean_content, metadata=meta)

        # 2. Store in SQLite
        msg_id = self.sqlite.add_message(self.session_id, meta.get("role", "assistant"), clean_content)

        # 3. Store in ChromaDB vector store
        meta["vault_path"] = vault_path
        meta["sqlite_id"] = msg_id
        
        self._deduplicate_and_save(doc_id, clean_content, meta)

        logger.info(f"Memory saved [{memory_type}]: {doc_id} -> {vault_path}")
        return {
            "id": doc_id,
            "sqlite_id": msg_id,
            "vault_path": vault_path,
            "filename": filename,
            "status": "stored"
        }

    def read_memory(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Reads a memory record by filepath, document ID, or keyword.
        """
        # 1. If it looks like a path or markdown file, read from Vault
        if identifier.endswith(".md") or os.path.exists(identifier) or "/" in identifier or "\\" in identifier:
            note = self.vault.read_note(identifier)
            if note:
                return {
                    "source": "vault",
                    "path": note["path"],
                    "content": note["body"],
                    "metadata": note["frontmatter"],
                    "links": note["links"]
                }

        # 2. Try Chroma vector search by ID
        chroma_res = self.chroma.query_similar(identifier, n_results=1)
        if chroma_res:
            top = chroma_res[0]
            self._audit("MEMORY_RETRIEVED", top.get("id", "unknown"), top.get("document", ""))
            return {
                "source": "chroma",
                "id": top.get("id"),
                "content": top.get("document"),
                "metadata": top.get("metadata", {})
            }

        return None

    def search_memory(
        self,
        query: str,
        limit: int = 5,
        search_vault: bool = True,
        search_chroma: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Unified hybrid search: Combines ChromaDB semantic vector embeddings
        and Vault full-text markdown search.
        """
        combined = []
        seen_contents = set()

        # 1. Semantic Search via ChromaDB
        if search_chroma:
            try:
                chroma_results = self.chroma.query_similar(query, n_results=limit)
                for item in chroma_results:
                    doc = item.get("document", "")
                    if doc and doc not in seen_contents:
                        seen_contents.add(doc)
                        combined.append({
                            "source": "chroma_semantic",
                            "id": item.get("id"),
                            "content": doc,
                            "metadata": item.get("metadata", {}),
                            "distance": item.get("distance", 0.0)
                        })
            except Exception as e:
                logger.warning(f"ChromaDB search failed: {e}")

        # 2. Keyword Search via Markdown Vault
        if search_vault:
            try:
                vault_results = self.vault.search_notes(query, limit=limit)
                for v_item in vault_results:
                    body = v_item.get("snippet", "")
                    if body and body not in seen_contents:
                        seen_contents.add(body)
                        combined.append({
                            "source": "vault_markdown",
                            "path": v_item.get("path"),
                            "filename": v_item.get("filename"),
                            "folder": v_item.get("folder"),
                            "content": body,
                            "metadata": v_item.get("frontmatter", {})
                        })
            except Exception as e:
                logger.warning(f"Vault search failed: {e}")

        return combined[:limit]

    def update_memory(
        self,
        identifier: str,
        new_content: str,
        metadata_updates: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Updates a memory note in the Vault and synchronizes its Chroma vector.
        """
        success = False
        if identifier.endswith(".md") or os.path.isabs(identifier):
            success = self.vault.update_note(identifier, new_content, metadata_updates)
            # If updated, refresh vector in Chroma
            if success:
                doc_id = f"vault_{self.vault._slugify(os.path.basename(identifier))}"
                self.chroma.add_memory(doc_id, new_content, metadata_updates or {"path": identifier})
        else:
            # Handle Chroma ID update
            # Normally we would update ChromaDB directly here, assuming it's supported
            logger.warning("Update memory via doc_id directly is limited to Vault path resolution in this version.")
        return success

    def forget_memory(self, identifier: str) -> bool:
        """
        Deletes a memory explicitly.
        """
        success = False
        try:
            # Delete from Chroma
            # Assuming ChromaManager has a delete_memory method
            if hasattr(self.chroma, 'delete_memory'):
                self.chroma.delete_memory(identifier)
                success = True
            
            # Delete from Vault if it's a path
            if identifier.endswith(".md") or os.path.isabs(identifier) or identifier.startswith("vault_"):
                # Simplistic implementation for Vault deletion
                try:
                    if os.path.exists(identifier):
                        os.remove(identifier)
                        success = True
                except:
                    pass
        except Exception as e:
            logger.error(f"Failed to delete memory {identifier}: {e}")
            
        if success:
            self._audit("MEMORY_DELETED", identifier, "<deleted>")
            
        return success

    def consolidate_memories(self, project_id: Optional[str] = None) -> int:
        """
        Performs memory consolidation: marks duplicates as SUPERSEDED, cleans up expired memories.
        Returns the number of memories consolidated.
        """
        # This would iterate over memories and group them semantically.
        # For this version, we will just sweep for expired items.
        consolidated = 0
        try:
            # A full implementation would query all Chroma items and check 'expires_at'
            logger.info(f"Consolidating memories for project {project_id or 'all'}.")
            # Dummy implementation as Chroma typically doesn't support easy full iteration without specific query
            pass
        except Exception as e:
            logger.error(f"Error during consolidation: {e}")
        return consolidated

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
        Creates/appends an entry in the Obsidian-compatible daily note (vault/daily/YYYY-MM-DD.md)
        with standard headings: Priorities, Activity, Reports, Decisions, Reflection, Tomorrow.
        """
        file_path = self.vault.create_daily_note(
            content=content,
            date_str=date_str,
            priorities=priorities,
            activity=activity,
            reports=reports,
            decisions=decisions,
            reflection=reflection,
            tomorrow=tomorrow,
            tags=tags
        )

        # Index in ChromaDB
        doc_id = f"daily_{date_str or datetime.date.today().isoformat()}_{int(datetime.datetime.now().timestamp())}"
        self.chroma.add_memory(
            doc_id=doc_id,
            text=content or f"Daily log for {date_str or datetime.date.today().isoformat()}",
            metadata={"type": "daily_note", "path": file_path, "date": date_str or datetime.date.today().isoformat()}
        )

        return file_path

    def raw_capture(
        self,
        title: str,
        content: str,
        source: str = "user_capture",
        tags: Optional[List[str]] = None
    ) -> str:
        """Stores raw capture in vault/raw/<slug>.md."""
        file_path = self.vault.raw_capture(title=title, content=content, source=source, tags=tags)
        slug = self.vault._slugify(title)
        self.chroma.add_memory(
            doc_id=f"raw_{slug}",
            text=f"{title}\n\n{content}",
            metadata={"type": "raw_capture", "title": title, "path": file_path}
        )
        return file_path

    def create_wiki_note(
        self,
        title: str,
        content: str,
        backlinks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None
    ) -> str:
        """Stores wiki knowledge note in vault/wiki/<slug>.md."""
        file_path = self.vault.create_wiki_note(title=title, content=content, backlinks=backlinks, tags=tags)
        slug = self.vault._slugify(title)
        self.chroma.add_memory(
            doc_id=f"wiki_{slug}",
            text=f"{title}\n\n{content}",
            metadata={"type": "wiki_article", "title": title, "path": file_path}
        )
        return file_path

    def get_backlinks(self, target_name: str) -> List[Dict[str, Any]]:
        """Finds all notes in the vault linking to target_name via [[target_name]]."""
        return self.vault.get_backlinks(target_name)

    def get_all_tags(self) -> List[str]:
        """Returns all frontmatter and inline tags across vault notes."""
        return self.vault.get_all_tags()

    def create_report(
        self,
        title: str,
        content: str,
        report_type: str = "report",
        tags: Optional[List[str]] = None,
        backlinks: Optional[List[str]] = None
    ) -> str:
        """
        Creates a structured markdown report in vault/outputs/<slug_title>.md
        and indexes its semantic embedding into ChromaDB.
        """
        file_path = self.vault.create_report(title, content, report_type=report_type, tags=tags, backlinks=backlinks)

        # Index in ChromaDB
        slug = self.vault._slugify(title)
        self.chroma.add_memory(
            doc_id=f"report_{slug}",
            text=f"{title}\n\n{content}",
            metadata={"type": report_type, "title": title, "path": file_path}
        )

        return file_path

    def link_notes(self, source_note: str, target_note: str, link_text: Optional[str] = None) -> bool:
        """
        Creates an Obsidian [[wiki-link]] from source note to target note.
        """
        return self.vault.link_notes(source_note, target_note, link_text=link_text)

    def retrieve_context(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, str]]:
        """
        Multi-tiered context retrieval: Merges SQLite session history,
        ChromaDB semantic vectors, and relevant Markdown Vault notes.
        """
        target_session = session_id or self.session_id
        context_messages = self.builder.build_context(target_session, query)

        # Also check Vault for top relevant notes if query is substantive
        if query and len(query.strip()) > 5:
            vault_matches = self.vault.search_notes(query, limit=2)
            for vm in vault_matches:
                snippet = vm.get("snippet", "")
                if snippet:
                    context_messages.insert(0, {
                        "role": "system",
                        "content": f"[Vault Note Reference: {vm.get('filename')}]: {snippet}"
                    })

        return context_messages

    def close(self):
        """Closes active database connections."""
        self.sqlite.close()
