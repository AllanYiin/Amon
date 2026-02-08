import json
import os
import tempfile
import unittest
from pathlib import Path

from amon.tooling.audit import FileAuditSink, _hash_payload, default_audit_log_path
from amon.tooling.types import ToolCall, ToolResult


class ToolingAuditTests(unittest.TestCase):
    def test_file_audit_sink_redacts_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "tool_audit.jsonl"
            sink = FileAuditSink(log_path)
            call = ToolCall(
                tool="filesystem.read",
                args={"path": "/tmp/secret.txt", "token": "secret-value"},
                caller="tests",
                project_id="proj-1",
                session_id="session-1",
            )
            result = ToolResult(
                content=[{"type": "text", "text": "secret-result"}],
                is_error=False,
                meta={"status": "ok"},
            )
            sink.record(call, result, "allow", duration_ms=12, source="builtin")
            payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["tool"], call.tool)
            self.assertEqual(payload["decision"], "allow")
            self.assertEqual(payload["duration_ms"], 12)
            self.assertEqual(payload["source"], "builtin")
            self.assertEqual(payload["args_sha256"], _hash_payload(call.args))
            self.assertEqual(
                payload["result_sha256"],
                _hash_payload({"content": result.content, "is_error": False, "meta": result.meta}),
            )
            self.assertNotIn("secret-value", json.dumps(payload, ensure_ascii=False))
            self.assertNotIn("secret-result", json.dumps(payload, ensure_ascii=False))

    def test_default_audit_log_path_respects_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            original_home = os.environ.get("AMON_HOME")
            os.environ["AMON_HOME"] = temp_dir
            try:
                path = default_audit_log_path()
            finally:
                if original_home is None:
                    os.environ.pop("AMON_HOME", None)
                else:
                    os.environ["AMON_HOME"] = original_home
            self.assertEqual(path, Path(temp_dir) / "logs" / "tool_audit.jsonl")


if __name__ == "__main__":
    unittest.main()
