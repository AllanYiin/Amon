import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
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

    def test_mcp_cache_uses_cached_tools(self) -> None:
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
                cache_dir = Path(temp_dir) / "cache" / "mcp"
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_payload = {
                    "transport": "stdio",
                    "tools": [{"name": "cached", "description": "cached tool"}],
                    "updated_at": "cached",
                }
                cache_path = cache_dir / "stub.json"
                cache_path.write_text(json.dumps(cache_payload, ensure_ascii=False), encoding="utf-8")

                registry = core.get_mcp_registry()
                tools = registry["servers"]["stub"].get("tools", [])
                self.assertTrue(any(tool.get("name") == "cached" for tool in tools))
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_mcp_allowed_tools_enforced(self) -> None:
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
                    },
                )
                core.set_config_value("mcp.allowed_tools", ["stub:other"])
                with self.assertRaises(PermissionError) as ctx:
                    core.call_mcp_tool("stub", "echo", {"text": "hello"})
                self.assertIn("DENIED_BY_POLICY", str(ctx.exception))
            finally:
                os.environ.pop("AMON_HOME", None)


    def test_mcp_tool_none_result_is_normalized(self) -> None:
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
                with patch("amon.core.MCPStdioClient.call_tool", return_value=None):
                    result = core.call_mcp_tool("stub", "echo", {"text": "hello"})
                self.assertIsInstance(result, dict)
                self.assertEqual(result.get("data"), {})
                self.assertFalse(result.get("is_error"))
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_mcp_tool_error_result(self) -> None:
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
                    },
                )
                result = core.call_mcp_tool("stub", "fail", {})
                self.assertTrue(result.get("is_error"))
                content = result.get("data", {}).get("content", [])
                self.assertTrue(any(item.get("text") == "stub failure" for item in content))
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
