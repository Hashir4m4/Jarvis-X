import unittest
import sys
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy deps
sys.modules['chromadb'] = MagicMock()

from backend.agents import code_tools
from backend.agents.planner import Planner
from backend.agents.coder import Coder
from backend.agents.reviewer import Reviewer
from backend.agents.executor import Executor


class TestCodeTools(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create a small test repo
        os.makedirs(os.path.join(self.test_dir, "src"))
        with open(os.path.join(self.test_dir, "src", "main.py"), "w") as f:
            f.write("import os\nimport sys\n\ndef main():\n    print('hello')\n")
        with open(os.path.join(self.test_dir, "requirements.txt"), "w") as f:
            f.write("requests\nflask\n")

    def test_detect_language(self):
        self.assertEqual(code_tools.detect_language("main.py"), "python")
        self.assertEqual(code_tools.detect_language("app.js"), "javascript")
        self.assertEqual(code_tools.detect_language("lib.rs"), "rust")
        self.assertEqual(code_tools.detect_language("Main.java"), "java")
        self.assertEqual(code_tools.detect_language("photo.png"), "unknown")

    def test_scan_repository(self):
        files = code_tools.scan_repository(self.test_dir)
        names = [f["path"] for f in files]
        self.assertTrue(any("main.py" in n for n in names))
        self.assertTrue(any("requirements.txt" in n for n in names))

    def test_build_repo_tree(self):
        tree = code_tools.build_repo_tree(self.test_dir)
        self.assertIn("src", tree)
        self.assertIn("main.py", tree)

    def test_extract_imports(self):
        filepath = os.path.join(self.test_dir, "src", "main.py")
        imports = code_tools.extract_imports(filepath)
        self.assertEqual(len(imports), 2)
        self.assertIn("import os", imports)

    def test_analyze_dependencies(self):
        deps = code_tools.analyze_dependencies(self.test_dir)
        self.assertIn("requirements.txt", deps)
        self.assertIn("requests", deps["requirements.txt"])

    def test_read_and_write(self):
        path = os.path.join(self.test_dir, "output.txt")
        code_tools.write_file_content(path, "hello world")
        content = code_tools.read_file_content(path)
        self.assertEqual(content, "hello world")

    def tearDown(self):
        shutil.rmtree(self.test_dir)


class TestPlanner(unittest.TestCase):
    def test_parse_steps(self):
        planner = Planner(MagicMock())
        raw = (
            "STEP 1: CREATE | file=src/utils.py | description=Create utility module\n"
            "STEP 2: MODIFY | file=src/main.py | description=Add imports\n"
            "STEP 3: TEST | file=tests/test_utils.py | description=Run tests\n"
        )
        steps = planner._parse_steps(raw)
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]["action"], "CREATE")
        self.assertEqual(steps[0]["file"], "src/utils.py")
        self.assertEqual(steps[1]["action"], "MODIFY")
        self.assertEqual(steps[2]["action"], "TEST")


class TestCoder(unittest.TestCase):
    def test_extract_code_with_fences(self):
        coder = Coder(MagicMock())
        response = "Here is the code:\n```python\ndef hello():\n    print('hi')\n```\nDone."
        code = coder._extract_code(response)
        self.assertIn("def hello():", code)
        self.assertNotIn("```", code)
        self.assertNotIn("Here is", code)

    def test_extract_code_without_fences(self):
        coder = Coder(MagicMock())
        response = "def hello():\n    print('hi')"
        code = coder._extract_code(response)
        self.assertEqual(code, "def hello():\n    print('hi')")


class TestReviewer(unittest.TestCase):
    def test_parse_review_pass(self):
        reviewer = Reviewer(MagicMock())
        raw = (
            "VERDICT: PASS\n\n"
            "ISSUES: None\n\n"
            "SUGGESTIONS:\n"
            "- Consider adding type hints\n"
        )
        result = reviewer._parse_review(raw)
        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(len(result["issues"]), 0)
        self.assertEqual(len(result["suggestions"]), 1)

    def test_parse_review_fail(self):
        reviewer = Reviewer(MagicMock())
        raw = (
            "VERDICT: FAIL\n\n"
            "ISSUES:\n"
            "- Missing error handling in main()\n"
            "- No input validation\n\n"
            "SUGGESTIONS:\n"
            "- Add try/except blocks\n"
        )
        result = reviewer._parse_review(raw)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(len(result["suggestions"]), 1)


class TestExecutor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    @patch('builtins.input', return_value='y')
    def test_run_python_file(self, mock_input):
        filepath = os.path.join(self.test_dir, "hello.py")
        with open(filepath, "w") as f:
            f.write("print('Hello from executor')")

        executor = Executor(self.test_dir)
        result = executor.run_file(filepath, "python")
        self.assertEqual(result["status"], "ok")
        self.assertIn("Hello from executor", result["stdout"])

    @patch('builtins.input', return_value='y')
    def test_lint_python(self, mock_input):
        filepath = os.path.join(self.test_dir, "valid.py")
        with open(filepath, "w") as f:
            f.write("x = 1\n")

        executor = Executor(self.test_dir)
        result = executor.lint(filepath, "python")
        self.assertEqual(result["status"], "ok")

    def tearDown(self):
        shutil.rmtree(self.test_dir)


if __name__ == "__main__":
    unittest.main()
