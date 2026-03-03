from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class ValidateAllV3GraphsTests(unittest.TestCase):
    def test_validate_all_v3_graphs_script(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "validate_all_v3_graphs.py"
        result = subprocess.run([sys.executable, str(script)], check=False, capture_output=True, text=True)
        if result.returncode != 0:
            self.fail(result.stdout + "\n" + result.stderr)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
