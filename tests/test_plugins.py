import unittest
import sys
import os
import tempfile
import shutil
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.plugins.plugin_sandbox import PluginSandbox
from backend.plugins.plugin_manager import PluginManager

class TestPluginSandbox(unittest.TestCase):
    
    def test_safe_code(self):
        code = "def hello():\n    return 'Hello World'\n"
        self.assertTrue(PluginSandbox.check_source(code))

    def test_blacklisted_import(self):
        code = "import os\n\ndef evil():\n    os.system('rm -rf /')\n"
        with self.assertRaises(ValueError) as context:
            PluginSandbox.check_source(code)
        self.assertIn("Blacklisted import detected: os", str(context.exception))

    def test_blacklisted_from_import(self):
        code = "from subprocess import Popen\n"
        with self.assertRaises(ValueError) as context:
            PluginSandbox.check_source(code)
        self.assertIn("Blacklisted from-import detected: subprocess", str(context.exception))

    def test_forbidden_eval(self):
        code = "def parse(val):\n    return eval(val)\n"
        with self.assertRaises(ValueError) as context:
            PluginSandbox.check_source(code)
        self.assertIn("Forbidden built-in function detected: eval", str(context.exception))


class TestPluginManager(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
        # Create a valid plugin
        self.valid_plugin_dir = os.path.join(self.test_dir, "valid_plugin")
        os.makedirs(self.valid_plugin_dir)
        
        with open(os.path.join(self.valid_plugin_dir, "plugin.json"), "w") as f:
            json.dump({"name": "Test", "version": "1.0"}, f)
            
        with open(os.path.join(self.valid_plugin_dir, "main.py"), "w") as f:
            f.write(
                "from backend.plugins.base_plugin import BasePlugin\n\n"
                "class MyPlugin(BasePlugin):\n"
                "    def get_tools(self):\n"
                "        return [{'name': 'test_tool', 'description': 'test tool'}]\n"
                "    def execute(self, tool_name, kwargs):\n"
                "        return 'success'\n"
            )

        # Create a malicious plugin
        self.evil_plugin_dir = os.path.join(self.test_dir, "evil_plugin")
        os.makedirs(self.evil_plugin_dir)
        
        with open(os.path.join(self.evil_plugin_dir, "plugin.json"), "w") as f:
            json.dump({"name": "Evil", "version": "1.0"}, f)
            
        with open(os.path.join(self.evil_plugin_dir, "main.py"), "w") as f:
            f.write(
                "import os\n"
                "from backend.plugins.base_plugin import BasePlugin\n\n"
                "class EvilPlugin(BasePlugin):\n"
                "    def get_tools(self):\n"
                "        return []\n"
                "    def execute(self, t, k):\n"
                "        pass\n"
            )

    def test_plugin_discovery_and_sandbox(self):
        manager = PluginManager(self.test_dir)
        manager.discover_and_load()
        
        # Valid plugin should be loaded
        self.assertIn("valid_plugin", manager.loaded_plugins)
        
        # Evil plugin should be blocked by sandbox
        self.assertNotIn("evil_plugin", manager.loaded_plugins)

    def test_tool_aggregation_and_execution(self):
        manager = PluginManager(self.test_dir)
        manager.discover_and_load()
        
        tools = manager.get_all_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "test_tool")
        
        result = manager.execute_tool("test_tool", {})
        self.assertEqual(result, "success")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

if __name__ == "__main__":
    unittest.main()
