import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph2.node_executor import ExtractionError, extract_output


class TaskGraph2OutputExtractionTests(unittest.TestCase):
    def test_extract_output_parses_json_full_text(self) -> None:
        payload = extract_output('{"name":"amon","count":2}', "json")
        self.assertEqual(payload["name"], "amon")
        self.assertEqual(payload["count"], 2)

    def test_extract_output_best_effort_extracts_object_snippet(self) -> None:
        text = "前言\n```json\n{\"ok\": true, \"items\": [1,2]}\n```\n結尾"
        payload = extract_output(text, "json")
        self.assertEqual(payload, {"ok": True, "items": [1, 2]})

    def test_extract_output_best_effort_extracts_array_snippet(self) -> None:
        text = "answer: [1, 2, 3] done"
        payload = extract_output(text, "json")
        self.assertEqual(payload, [1, 2, 3])

    def test_extract_output_raises_diagnostic_error_when_failed(self) -> None:
        with self.assertRaises(ExtractionError) as ctx:
            extract_output("nothing parseable here", "json")
        self.assertIn("length=", str(ctx.exception))
        self.assertIn("object_start=", str(ctx.exception))
        self.assertIn("array_start=", str(ctx.exception))

    def test_extract_output_keeps_non_json_type_text(self) -> None:
        text = "plain markdown"
        self.assertEqual(extract_output(text, "md"), text)


if __name__ == "__main__":
    unittest.main()
