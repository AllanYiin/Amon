import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon import cli


class CliInitSandboxTests(unittest.TestCase):
    def test_build_parser_supports_start_sandbox_flag(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["init", "--start-sandbox"])
        self.assertEqual(args.command, "init")
        self.assertTrue(args.start_sandbox)

    @patch("amon.cli._launch_sandbox_terminal", return_value=(True, "windows-cmd"))
    def test_main_init_with_start_sandbox_launches_terminal(self, mock_launch) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            original_argv = sys.argv
            sys.argv = ["amon", "init", "--start-sandbox"]
            buffer = io.StringIO()
            try:
                with redirect_stdout(buffer):
                    cli.main()
            finally:
                sys.argv = original_argv
                os.environ.pop("AMON_HOME", None)

        output = buffer.getvalue()
        self.assertIn("已完成初始化", output)
        self.assertIn("已嘗試另開 command 視窗啟動 sandbox runner", output)
        mock_launch.assert_called_once()

    @patch("amon.cli._launch_sandbox_terminal", return_value=(False, "no_supported_terminal"))
    def test_main_init_with_start_sandbox_prints_fallback_message(self, mock_launch) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            original_argv = sys.argv
            sys.argv = ["amon", "init", "--start-sandbox"]
            buffer = io.StringIO()
            try:
                with redirect_stdout(buffer):
                    cli.main()
            finally:
                sys.argv = original_argv
                os.environ.pop("AMON_HOME", None)

        output = buffer.getvalue()
        self.assertIn("無法自動開啟 command 視窗", output)
        self.assertIn("請手動執行 amon-sandbox-runner", output)
        mock_launch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
