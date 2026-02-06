import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from amon.tooling import load_tool_spec, ToolingError


class ToolSpecValidationTests(unittest.TestCase):
    def test_rejects_non_list_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir)
            payload = {
                "name": "demo",
                "version": "0.1.0",
                "inputs_schema": {},
                "outputs_schema": {},
                "risk_level": "low",
                "allowed_paths": "workspace",
            }
            (tool_dir / "tool.yaml").write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaises(ToolingError):
                load_tool_spec(tool_dir)


if __name__ == "__main__":
    unittest.main()
