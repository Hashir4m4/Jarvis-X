import unittest
import os
import sys
import tempfile
import shutil
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.memory.vault.vault_manager import VaultManager
from backend.memory.memory_api import MemoryAPI


class TestObsidianVaultIntegration(unittest.TestCase):
    def setUp(self):
        self.test_vault_dir = tempfile.mkdtemp()
        self.vault = VaultManager(vault_root=self.test_vault_dir)

    def tearDown(self):
        shutil.rmtree(self.test_vault_dir, ignore_errors=True)

    def test_configurable_vault_and_directory_conventions(self):
        """Verify configurable vault path and standard conventions (raw, wiki, outputs, daily)."""
        self.assertTrue(os.path.isdir(os.path.join(self.test_vault_dir, "raw")))
        self.assertTrue(os.path.isdir(os.path.join(self.test_vault_dir, "wiki")))
        self.assertTrue(os.path.isdir(os.path.join(self.test_vault_dir, "outputs")))
        self.assertTrue(os.path.isdir(os.path.join(self.test_vault_dir, "daily")))

    def test_structured_daily_note_conventions(self):
        """
        Verify daily notes follow the standard Obsidian convention:
        # Daily Log
        ## Priorities
        ## Activity
        ## Reports
        ## Decisions
        ## Reflection
        ## Tomorrow
        """
        date_str = "2026-08-29"
        note_path = self.vault.create_daily_note(
            date_str=date_str,
            priorities=["Complete vault integration", "Run test suite", "Ship update"],
            activity=["Refactored memory architecture", "Added path traversal protection"],
            reports=["Vault Performance Report"],
            decisions=["Standardize on Obsidian Markdown conventions"],
            reflection="Productive execution across all submodules.",
            tomorrow=["Review morning brief", "Validate telemetry stream"],
            tags=["daily", "sprint_goal"]
        )

        self.assertTrue(os.path.isfile(note_path))
        self.assertEqual(os.path.basename(note_path), "2026-08-29.md")

        note_data = self.vault.read_note(note_path)
        self.assertIsNotNone(note_data)

        # Check frontmatter
        fm = note_data["frontmatter"]
        self.assertEqual(fm.get("type"), "daily_note")
        self.assertEqual(fm.get("date"), date_str)
        self.assertIn("daily", fm.get("tags", []))

        # Check standard headings
        raw = note_data["raw"]
        self.assertIn("# Daily Log — 2026-08-29", raw)
        self.assertIn("## Priorities", raw)
        self.assertIn("Complete vault integration", raw)
        self.assertIn("## Activity", raw)
        self.assertIn("## Reports", raw)
        self.assertIn("## Decisions", raw)
        self.assertIn("## Reflection", raw)
        self.assertIn("## Tomorrow", raw)

    def test_reports_outputs_convention(self):
        """Verify structured reports are saved to vault/outputs/ with metadata."""
        report_path = self.vault.create_report(
            title="Q3 Autonomous Agent Analysis",
            content="Summary of multi-agent swarm telemetry and task throughput.",
            report_type="agent_analysis",
            tags=["report", "agents", "analytics"]
        )

        self.assertTrue(os.path.isfile(report_path))
        self.assertIn(os.path.join("outputs", "q3_autonomous_agent_analysis.md"), report_path)

        note_data = self.vault.read_note(report_path)
        self.assertEqual(note_data["frontmatter"].get("type"), "agent_analysis")
        self.assertIn("Summary of multi-agent swarm", note_data["body"])

    def test_raw_captures_convention(self):
        """Verify quick thoughts and captures are stored in vault/raw/."""
        raw_path = self.vault.raw_capture(
            title="Quick Spark Idea",
            content="Integrate Whisper push-to-talk directly into the central router.",
            tags=["idea", "raw_capture"]
        )

        self.assertTrue(os.path.isfile(raw_path))
        self.assertIn(os.path.join("raw", "quick_spark_idea.md"), raw_path)

        note_data = self.vault.read_note(raw_path)
        self.assertEqual(note_data["frontmatter"].get("type"), "raw_capture")
        self.assertIn("Whisper push-to-talk", note_data["body"])

    def test_wiki_knowledge_and_backlinks(self):
        """Verify wiki notes, backlinks discovery, and Obsidian [[links]]."""
        # Create target topic note
        target_path = self.vault.create_wiki_note(
            title="Agent Architecture",
            content="Core multi-agent coordination principles for JARVIS OS.",
            tags=["architecture", "wiki"]
        )

        # Create referencing note linking to [[Agent Architecture]]
        ref_path = self.vault.create_wiki_note(
            title="Router Design",
            content="The router coordinates execution with the [[Agent Architecture]] subsystem.",
            backlinks=["Agent Architecture"],
            tags=["router", "wiki"]
        )

        # Verify backlinks extraction
        backlinks = self.vault.get_backlinks("Agent Architecture")
        self.assertTrue(len(backlinks) >= 1)
        self.assertIn("router_design.md", backlinks[0]["source_filename"])

    def test_tags_aggregation(self):
        """Verify frontmatter and inline tags aggregation."""
        self.vault.raw_capture("Snippet 1", "This is an #engineering note.", tags=["hardware", "sensors"])
        self.vault.create_report("Report 1", "Report text with #telemetry tag.", tags=["performance"])

        all_tags = self.vault.get_all_tags()
        self.assertIn("hardware", all_tags)
        self.assertIn("sensors", all_tags)
        self.assertIn("performance", all_tags)
        self.assertIn("engineering", all_tags)
        self.assertIn("telemetry", all_tags)

    def test_path_traversal_prevention(self):
        """Verify strict protection against directory traversal."""
        # Attempt to access or write outside vault
        with self.assertRaises(ValueError):
            self.vault._safe_resolve_path("../../outside.md")

        with self.assertRaises(ValueError):
            self.vault.write_note("../", "evil.md", "Malicious content")

        with self.assertRaises(ValueError):
            self.vault.create_daily_note(date_str="../../../etc/passwd")

    def test_obsidian_independence(self):
        """Verify reading and writing markdown operates completely independent of Obsidian app."""
        file_path = self.vault.write_note("wiki", "StandAlone.md", "Standalone knowledge test.")
        self.assertTrue(os.path.isfile(file_path))

        note = self.vault.read_note(file_path)
        self.assertIsNotNone(note)
        self.assertIn("Standalone knowledge test.", note["body"])


if __name__ == "__main__":
    unittest.main()
