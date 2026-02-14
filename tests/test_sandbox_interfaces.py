import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.sandbox import parse_sandbox_config, validate_relative_path


class SandboxInterfacesTests(unittest.TestCase):
    def test_parse_sandbox_config_defaults(self) -> None:
        parsed = parse_sandbox_config({})
        self.assertFalse(parsed.enabled)
        self.assertEqual(parsed.runner_url, "http://127.0.0.1:8088")
        self.assertEqual(parsed.default_image, "python:3.12-slim")
        self.assertEqual(parsed.timeout_seconds, 30)

    def test_parse_sandbox_config_overrides(self) -> None:
        parsed = parse_sandbox_config(
            {
                "sandbox": {
                    "enabled": True,
                    "runner_url": "http://runner.internal:18088",
                    "memory_mb": 1024,
                    "cpu_cores": 2,
                    "max_stdout_kb": 512,
                }
            }
        )
        self.assertTrue(parsed.enabled)
        self.assertEqual(parsed.runner_url, "http://runner.internal:18088")
        self.assertEqual(parsed.memory_mb, 1024)
        self.assertEqual(parsed.cpu_cores, 2.0)
        self.assertEqual(parsed.max_stdout_kb, 512)

    def test_validate_relative_path_accepts_simple_relative(self) -> None:
        self.assertEqual(validate_relative_path("workspace/output/report.json"), "workspace/output/report.json")
        self.assertEqual(validate_relative_path(" workspace\\output\\result.txt "), "workspace/output/result.txt")

    def test_validate_relative_path_rejects_invalid_inputs(self) -> None:
        for sample in ("", "../escape", "/etc/passwd", "C:/Windows/system32", "a/./b", "a//b"):
            with self.assertRaises(ValueError, msg=sample):
                validate_relative_path(sample)


if __name__ == "__main__":
    unittest.main()
