from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from amon.artifacts.validators import run_validators


class ArtifactsValidatorsTests(unittest.TestCase):
    def test_python_validator_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-validators-") as tmpdir:
            file_path = Path(tmpdir) / "ok.py"
            file_path.write_text("print('ok')\n", encoding="utf-8")
            checks = run_validators(file_path)
            self.assertEqual(checks[0]["status"], "valid")

    def test_python_validator_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-validators-") as tmpdir:
            file_path = Path(tmpdir) / "bad.py"
            file_path.write_text("if True print('x')\n", encoding="utf-8")
            checks = run_validators(file_path)
            self.assertEqual(checks[0]["status"], "invalid")

    @patch("amon.artifacts.validators.shutil.which", return_value=None)
    def test_js_validator_skipped_without_node(self, _mock_which) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-validators-") as tmpdir:
            file_path = Path(tmpdir) / "x.js"
            file_path.write_text("const x = 1;\n", encoding="utf-8")
            checks = run_validators(file_path)
            self.assertEqual(checks[0]["status"], "skipped")

    @patch("amon.artifacts.validators.shutil.which", return_value=None)
    def test_ts_validator_skipped_without_tsc(self, _mock_which) -> None:
        with tempfile.TemporaryDirectory(prefix="amon-artifacts-validators-") as tmpdir:
            file_path = Path(tmpdir) / "x.ts"
            file_path.write_text("const x: number = 1;\n", encoding="utf-8")
            checks = run_validators(file_path)
            self.assertEqual(checks[0]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
