import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
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


if __name__ == "__main__":
    unittest.main()
