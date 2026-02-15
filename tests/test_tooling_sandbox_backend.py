import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class ToolingSandboxBackendTests(unittest.TestCase):
    def test_run_tool_uses_sandbox_backend_when_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Sandbox Tool 專案")
                project_path = Path(project.path)
                tool_dir = project_path / "tools" / "demo_sandbox"
                tool_dir.mkdir(parents=True, exist_ok=True)
                (tool_dir / "tool.py").write_text(
                    "import json, sys\npayload = json.loads(sys.stdin.read() or '{}')\nprint(payload.get('text', '').upper())\n",
                    encoding="utf-8",
                )
                (tool_dir / "tool.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "name": "demo_sandbox",
                            "version": "0.1.0",
                            "inputs_schema": {"type": "object"},
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                            "execution": {"backend": "sandbox"},
                        },
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )

                fake_summary = {
                    "exit_code": 0,
                    "timed_out": False,
                    "duration_ms": 55,
                    "stdout": "HELLO\n",
                    "stderr": "",
                    "manifest_path": str(project_path / "docs" / "artifacts" / "r1" / "tool_demo_sandbox" / "manifest.json"),
                }
                with patch("amon.core.run_sandbox_step", return_value=fake_summary) as run_step_mock:
                    output = core.run_tool("demo_sandbox", {"text": "hello"}, project_id=project.project_id)

                self.assertEqual(output["exit_code"], 0)
                self.assertEqual(output["stdout"], "HELLO\n")
                self.assertIn("manifest_path", output)
                self.assertEqual(run_step_mock.call_count, 1)
                kwargs = run_step_mock.call_args.kwargs
                self.assertEqual(kwargs["project_path"], project_path)
                self.assertEqual(kwargs["step_id"], "tool_demo_sandbox")
                self.assertTrue(kwargs["output_prefix"].startswith("docs/artifacts/"))
                self.assertTrue(kwargs["output_prefix"].endswith("/tool_demo_sandbox/"))
                self.assertIn("sys.stdin = io.StringIO", kwargs["code"])
                self.assertIn(json.dumps({"text": "hello"}, ensure_ascii=False), kwargs["code"])
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_run_tool_without_execution_block_keeps_host_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Host Tool 專案")
                project_path = Path(project.path)
                tool_dir = project_path / "tools" / "demo_host"
                tool_dir.mkdir(parents=True, exist_ok=True)
                (tool_dir / "tool.py").write_text("print('ok')\n", encoding="utf-8")
                (tool_dir / "tool.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "name": "demo_host",
                            "version": "0.1.0",
                            "inputs_schema": {"type": "object"},
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        },
                        allow_unicode=True,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )

                with patch("amon.core.run_tool_process", return_value={"status": "ok"}) as host_mock:
                    output = core.run_tool("demo_host", {}, project_id=project.project_id)

                self.assertEqual(output, {"status": "ok"})
                self.assertEqual(host_mock.call_count, 1)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
