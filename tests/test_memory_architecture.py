import unittest
import sys
import os
import tempfile
import shutil
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy external modules
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()

from backend.memory.vault.vault_manager import VaultManager
from backend.memory.memory_api import MemoryAPI
from backend.memory_manager import MemoryManager


class TestMemoryArchitecture(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sqlite_db = os.path.join(self.test_dir, "test_jarvis.sqlite")
        self.vault_dir = os.path.join(self.test_dir, "vault")

        self.config = {
            "memory_advanced": {
                "sqlite_db_path": self.sqlite_db,
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": self.vault_dir
            }
        }
        self.memory_api = MemoryAPI(self.config, session_id="test_mem_session")

    def tearDown(self):
        self.memory_api.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_vault_directory_creation(self):
        """Verify vault subdirectories are initialized."""
        self.assertTrue(os.path.isdir(os.path.join(self.vault_dir, "raw")))
        self.assertTrue(os.path.isdir(os.path.join(self.vault_dir, "wiki")))
        self.assertTrue(os.path.isdir(os.path.join(self.vault_dir, "outputs")))
        self.assertTrue(os.path.isdir(os.path.join(self.vault_dir, "daily")))

    def test_create_and_append_daily_note(self):
        """Verify Obsidian daily note creation with YAML frontmatter and appending."""
        date_str = "2026-09-03"
        path = self.memory_api.create_daily_note("First morning update", date_str=date_str, tags=["test", "morning"])
        self.assertTrue(os.path.isfile(path))

        # Read back
        note = self.memory_api.vault.read_note(path)
        self.assertEqual(note["frontmatter"]["type"], "daily_note")
        self.assertEqual(note["frontmatter"]["date"], date_str)
        self.assertIn("First morning update", note["body"])

        # Append to same daily note
        self.memory_api.create_daily_note("Evening status check", date_str=date_str)
        note_updated = self.memory_api.vault.read_note(path)
        self.assertIn("First morning update", note_updated["body"])
        self.assertIn("Evening status check", note_updated["body"])

    def test_create_report(self):
        """Verify Obsidian report creation in vault/outputs/."""
        title = "Weekly System Performance Review"
        content = "## Summary\nAll subsystems operated at 99.9% uptime with 0 critical security alerts."
        report_path = self.memory_api.create_report(title, content, report_type="system_audit", tags=["audit", "weekly"])

        self.assertTrue(os.path.isfile(report_path))
        note = self.memory_api.vault.read_note(report_path)
        self.assertEqual(note["frontmatter"]["title"], title)
        self.assertEqual(note["frontmatter"]["type"], "system_audit")
        self.assertIn("99.9% uptime", note["body"])

    def test_write_and_read_memory(self):
        """Verify write_memory across Vault and SQLite."""
        res = self.memory_api.write_memory(
            content="User prefers dark mode UI and fast streaming responses.",
            memory_type="user_preference",
            category="wiki",
            title="UI Preferences"
        )
        self.assertEqual(res["status"], "stored")
        self.assertTrue(os.path.isfile(res["vault_path"]))

        # Read back via path
        read_res = self.memory_api.read_memory(res["vault_path"])
        self.assertEqual(read_res["source"], "vault")
        self.assertIn("dark mode UI", read_res["content"])
        self.assertEqual(read_res["metadata"]["type"], "user_preference")

    def test_link_notes(self):
        """Verify Obsidian [[wiki-link]] creation."""
        note_a = self.memory_api.vault.write_note("wiki", "project_alpha.md", "# Project Alpha\nMain description.")
        self.memory_api.link_notes(note_a, "target_architecture", link_text="Architecture Spec")

        read_note = self.memory_api.vault.read_note(note_a)
        self.assertIn("[[target_architecture|Architecture Spec]]", read_note["raw"])
        self.assertIn("target_architecture|Architecture Spec", read_note["links"])

    def test_search_memory_vault(self):
        """Verify full-text search across Vault Markdown documents."""
        self.memory_api.write_memory("Quantum key distribution enables provably secure encryption.", category="wiki", title="Quantum Info")
        self.memory_api.write_memory("Classical RSA encryption relies on prime factorization difficulty.", category="wiki", title="Classical RSA")

        results = self.memory_api.search_memory("Quantum key", limit=3, search_chroma=False)
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["source"], "vault_markdown")
        self.assertIn("provably secure encryption", results[0]["content"])

    def test_update_memory(self):
        """Verify updating existing vault note."""
        path = self.memory_api.vault.write_note("raw", "temp_note.md", "Initial temporary content.", metadata={"version": 1})
        success = self.memory_api.update_memory(path, "Updated revised content.", metadata_updates={"version": 2})

        self.assertTrue(success)
        updated = self.memory_api.vault.read_note(path)
        self.assertIn("Updated revised content.", updated["body"])
        self.assertEqual(int(updated["frontmatter"]["version"]), 2)

    def test_retrieve_context_with_vault(self):
        """Verify multi-tier retrieve_context combining SQLite session and Vault note references."""
        # Add a chat message
        self.memory_api.add_message("user", "Can you explain neural networks?")
        self.memory_api.add_message("assistant", "Neural networks are computational graphs inspired by the human brain.")

        # Create a vault note referencing neural networks
        self.memory_api.vault.write_note("wiki", "neural_nets.md", "Deep neural networks use backpropagation gradient descent.")

        context = self.memory_api.retrieve_context("neural networks", session_id="test_mem_session")
        self.assertTrue(len(context) >= 2)

        # Check that vault note reference was included
        vault_refs = [m for m in context if "Vault Note Reference" in m.get("content", "")]
        self.assertTrue(len(vault_refs) > 0)
        self.assertIn("neural_nets.md", vault_refs[0]["content"])

    def test_persistence_across_jarvis_restarts(self):
        """Verify memory persistence after shutting down and re-initializing JARVIS."""
        # 1. Write data into Session 1
        self.memory_api.create_daily_note("Entry before reboot", date_str="2026-09-03")
        self.memory_api.create_report("Reboot Persistence Report", "System state preserved across cycles.")
        self.memory_api.write_memory("Saved variable: API_ENDPOINT=http://localhost:8000", category="wiki", title="Config Key")
        self.memory_api.close()

        # 2. Re-instantiate MemoryManager (simulating JARVIS reboot)
        new_memory = MemoryManager(self.config, session_id="test_mem_session")

        # 3. Verify daily note persisted
        daily_note = new_memory.vault.read_note(os.path.join(self.vault_dir, "daily", "2026-09-03.md"))
        self.assertIsNotNone(daily_note)
        self.assertIn("Entry before reboot", daily_note["body"])

        # 4. Verify report persisted
        report_note = new_memory.vault.read_note(os.path.join(self.vault_dir, "outputs", "reboot_persistence_report.md"))
        self.assertIsNotNone(report_note)
        self.assertIn("System state preserved across cycles", report_note["body"])

        # 5. Verify search still finds persisted data
        search_res = new_memory.search_memory("API_ENDPOINT", search_chroma=False)
        self.assertTrue(len(search_res) > 0)
        self.assertIn("http://localhost:8000", search_res[0]["content"])

        new_memory.close()


if __name__ == "__main__":
    unittest.main()
