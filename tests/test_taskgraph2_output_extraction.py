import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.node_executor import OutputExtractionError, extract_output, validate_output
from amon.taskgraph2.schema import TaskNodeOutput


class TaskGraph2OutputExtractionTests(unittest.TestCase):
    def test_extract_output_json_direct_load(self) -> None:
        spec = TaskNodeOutput(type="json")
        payload = extract_output('{"ok": true, "count": 2}', spec)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["count"], 2)

    def test_extract_output_json_best_effort_with_noise(self) -> None:
        spec = TaskNodeOutput(type="json")
        raw = "前言說明\n```json\n{\"name\":\"amon\"}\n```\n尾聲"
        payload = extract_output(raw, spec)
        self.assertEqual(payload, {"name": "amon"})

    def test_extract_output_json_failure_contains_diagnostic(self) -> None:
        spec = TaskNodeOutput(type="json")
        with self.assertRaisesRegex(OutputExtractionError, "len="):
            extract_output("not-json", spec)

    def test_validate_output_required_keys_and_types(self) -> None:
        spec = TaskNodeOutput(type="json", schema={"required_keys": {"title": "string", "score": "number"}})
        validate_output({"title": "A", "score": 3.14}, spec)

    def test_validate_output_raises_on_missing_or_wrong_type(self) -> None:
        spec = TaskNodeOutput(type="json", schema={"required_keys": {"title": "string", "ok": "boolean"}})
        with self.assertRaisesRegex(Exception, "missing required key"):
            validate_output({"title": "A"}, spec)
        with self.assertRaisesRegex(Exception, "expected boolean"):
            validate_output({"title": "A", "ok": "yes"}, spec)


if __name__ == "__main__":
    unittest.main()
