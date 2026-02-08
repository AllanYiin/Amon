import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon import cli


class BuiltinToolsCliTests(unittest.TestCase):
    def test_list_and_run_builtin_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                output = self._run_cli(["tools", "list", "--builtin"])
                self.assertIn("builtin:filesystem.read", output)

                sample_path = Path(temp_dir) / "sample.txt"
                sample_path.write_text("hello", encoding="utf-8")
                run_output = self._run_cli(
                    [
                        "tools",
                        "run",
                        "filesystem.read",
                        "--builtin",
                        "--args",
                        json.dumps({"path": str(sample_path)}),
                    ]
                )
                payload = json.loads(run_output)
                self.assertEqual(payload.get("status"), "ok")
                self.assertEqual(payload.get("text"), "hello")
            finally:
                os.chdir(cwd)
                os.environ.pop("AMON_HOME", None)

    def _run_cli(self, args: list[str]) -> str:
        original_argv = sys.argv
        sys.argv = ["amon", *args]
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                cli.main()
        finally:
            sys.argv = original_argv
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
