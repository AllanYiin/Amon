import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class MCPToolsTests(unittest.TestCase):
    def test_mcp_stdio_list_and_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                stub_path = Path(__file__).with_name("mcp_stub_server.py")
                core.set_config_value(
                    "mcp.servers.stub",
                    {
                        "transport": "stdio",
                        "command": [sys.executable, str(stub_path)],
                        "allowed": ["echo"],
                    },
                )

                registry = core.refresh_mcp_registry()
                self.assertIn("stub", registry.get("servers", {}))
                tools = registry["servers"]["stub"].get("tools", [])
                self.assertTrue(any(tool.get("name") == "echo" for tool in tools))

                result = core.call_mcp_tool("stub", "echo", {"text": "hello"})
                self.assertEqual(result.get("data", {}).get("echo", {}).get("arguments", {}).get("text"), "hello")

                log_path = Path(temp_dir) / "logs" / "amon.log"
                log_text = log_path.read_text(encoding="utf-8")
                self.assertIn("\"event\": \"mcp_tool_call\"", log_text)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
