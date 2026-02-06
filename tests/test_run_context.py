import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.run.context import append_run_constraints, get_effective_constraints


class RunContextTests(unittest.TestCase):
    def test_rejects_invalid_run_id(self) -> None:
        with self.assertRaises(ValueError):
            append_run_constraints("../escape", ["keep it safe"])

    def test_rejects_invalid_run_id_on_read(self) -> None:
        with self.assertRaises(ValueError):
            get_effective_constraints("../escape")

    def test_append_and_read_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                run_id = "run-safe-1"
                run_dir = Path(temp_dir) / "projects" / "proj-1" / ".amon" / "runs" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                append_run_constraints(run_id, ["用繁體中文"])
                self.assertEqual(get_effective_constraints(run_id), ["用繁體中文"])
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
