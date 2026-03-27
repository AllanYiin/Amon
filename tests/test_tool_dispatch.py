import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.mcp_client import MCPServerConfig
from amon.models import decode_stream_event
from amon.tooling.types import ToolResult


class ToolDispatchTests(unittest.TestCase):
    def test_builtin_tool_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                fake_registry = Mock()
                fake_registry.call.return_value = ToolResult(
                    content=[{"type": "text", "text": "ok"}],
                    is_error=False,
                    meta={"status": "ok"},
                )
                with patch("amon.core.build_registry", return_value=fake_registry), patch("amon.core.emit_event") as emit_mock:
                    result = core.call_tool_unified("filesystem.read", {"path": "README.md"})
                self.assertEqual(result["content_text"], "ok")
                payload = emit_mock.call_args.args[0]["payload"]
                self.assertEqual(payload["route"], "builtin")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_mcp_tool_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                with patch.object(core, "call_mcp_tool", return_value={"is_error": False, "meta": {"status": "ok"}}), patch(
                    "amon.core.emit_event"
                ) as emit_mock:
                    result = core.call_tool_unified("server:echo", {"text": "hello"})
                self.assertFalse(result["is_error"])
                payload = emit_mock.call_args.args[0]["payload"]
                self.assertEqual(payload["route"], "mcp")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_toolforge_tool_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                with patch.object(core, "run_tool", return_value={"is_error": True, "meta": {"status": "denied"}}), patch(
                    "amon.core.emit_event"
                ) as emit_mock:
                    result = core.call_tool_unified("my_tool", {"x": 1}, project_id="p1")
                self.assertTrue(result["is_error"])
                self.assertEqual(result["meta"]["status"], "denied")
                payload = emit_mock.call_args.args[0]["payload"]
                self.assertEqual(payload["route"], "toolforge")
                self.assertEqual(payload["status"], "denied")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_call_mcp_tool_returns_content_text(self) -> None:
        class _FakeClient:
            def __init__(self, command) -> None:
                self.command = command

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def call_tool(self, name, arguments):
                return {
                    "content": [{"type": "text", "text": f"echo:{arguments.get('text', '')}"}],
                    "isError": False,
                }

        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                with patch.object(
                    core,
                    "load_config",
                    return_value={"mcp": {"allowed_tools": ["server:echo"]}},
                ), patch.object(
                    core,
                    "_load_mcp_servers",
                    return_value=[MCPServerConfig(name="server", transport="stdio", command=["fake-mcp"])],
                ), patch("amon.core.MCPStdioClient", _FakeClient):
                    result = core.call_mcp_tool("server", "echo", {"text": "hello"})

                self.assertFalse(result["is_error"])
                self.assertEqual(result["content_text"], "echo:hello")
                self.assertEqual(result["meta"]["status"], "ok")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_builtin_tool_dispatch_stream_event_includes_args_preview_and_error_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                fake_registry = Mock()
                fake_registry.call.return_value = ToolResult(
                    content=[{"type": "text", "text": "缺少 query 參數。"}],
                    is_error=True,
                    meta={"status": "invalid_args"},
                )
                streamed_tokens: list[str] = []
                with patch("amon.core.build_registry", return_value=fake_registry), patch("amon.core.emit_event"):
                    result = core.call_tool_unified(
                        "web.search",
                        {"query": "", "api_key": "secret-value"},
                        stream_handler=streamed_tokens.append,
                    )

                self.assertTrue(result["is_error"])
                tool_events = []
                for token in streamed_tokens:
                    is_event, payload = decode_stream_event(token)
                    if is_event and payload.get("event") == "tool_call":
                        tool_events.append(payload)
                self.assertEqual(len(tool_events), 2)
                self.assertEqual(tool_events[0].get("stage"), "start")
                self.assertIn('"query": ""', str(tool_events[0].get("args_preview") or ""))
                self.assertIn("[REDACTED]", str(tool_events[0].get("args_preview") or ""))
                self.assertEqual(tool_events[1].get("stage"), "complete")
                self.assertEqual(tool_events[1].get("status"), "invalid_args")
                self.assertEqual(tool_events[1].get("error_detail"), "缺少 query 參數。")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
