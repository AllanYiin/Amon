from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


class E2EPlanRunSmokeTests(unittest.TestCase):
    def test_e2e_plan_run_generates_required_artifacts(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "e2e_plan_run.sh"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "artifacts"
            subprocess.run(
                ["bash", str(script_path), "整理專案需求", str(output_dir)],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )

            required = ["graph.v3.json", "graph.mmd", "run.state.json", "events.jsonl"]
            for name in required:
                self.assertTrue((output_dir / name).exists(), f"missing artifact: {name}")


if __name__ == "__main__":
    unittest.main()
