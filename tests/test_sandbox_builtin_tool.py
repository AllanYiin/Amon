import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.tooling.builtins.sandbox import register_sandbox_tools
from amon.tooling.policy import ToolPolicy
from amon.tooling.registry import ToolRegistry
from amon.tooling.types import ToolCall


class SandboxBuiltinToolTests(unittest.TestCase):
    def test_sandbox_run_invokes_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            registry = ToolRegistry(policy=ToolPolicy(allow=("sandbox.run",)))
            register_sandbox_tools(registry, project_path=workspace, config={})

            with patch("amon.tooling.builtins.sandbox.run_sandbox_step") as run_mock:
                run_mock.return_value = {
                    "exit_code": 0,
                    "timed_out": False,
                    "duration_ms": 8,
                    "stdout": "ok",
                    "stderr": "",
                    "manifest_path": str(workspace / "audits" / "artifacts" / "manifest.json"),
                    "written_files": [],
                    "outputs": [],
                }
                result = registry.call(
                    ToolCall(tool="sandbox.run", args={"language": "bash", "code": "echo ok", "output_prefix": "audits/out/"}, caller="tester")
                )

            self.assertFalse(result.is_error)
            self.assertEqual(run_mock.call_count, 1)
            kwargs = run_mock.call_args.kwargs
            self.assertEqual(kwargs["language"], "bash")
            self.assertEqual(kwargs["project_path"], workspace)


if __name__ == "__main__":
    unittest.main()
