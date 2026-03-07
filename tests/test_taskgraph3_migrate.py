from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from amon import cli
from amon.taskgraph3.migrate import legacy_to_v3, validate_v3_graph_json, v2_to_v3


class TaskGraph3MigrateTests(unittest.TestCase):
    def test_legacy_fixture_converts_to_valid_v3(self) -> None:
        legacy_graph = {
            "nodes": [
                {"id": "N1", "type": "agent_task", "title": "分析", "description": "整理摘要"},
                {"id": "N2", "type": "write_file", "path": "docs/out.md", "content": "hello"},
            ],
            "edges": [{"from": "N1", "to": "N2"}],
        }

        converted = legacy_to_v3(legacy_graph)

        validate_v3_graph_json(converted)
        self.assertEqual(converted["version"], "taskgraph.v3")
        self.assertTrue(any(edge["kind"] == "DEPENDS_ON" for edge in converted["edges"]))
        self.assertTrue(any(node["node_type"] == "ARTIFACT" for node in converted["nodes"]))
        n1 = next(node for node in converted["nodes"] if node["id"] == "N1")
        self.assertEqual(n1["taskSpec"]["executor"], "agent")

    def test_v2_fixture_converts_to_valid_v3(self) -> None:
        v2_graph = {
            "schema_version": "2.0",
            "objective": "demo",
            "nodes": [
                {
                    "id": "T1",
                    "title": "step 1",
                    "kind": "agent",
                    "description": "first",
                    "writes": {"report": "docs/report.md"},
                    "output": {"type": "json"},
                    "guardrails": {"boundaries": ["workspace"], "require_human_approval": True},
                },
                {
                    "id": "T2",
                    "title": "step 2",
                    "kind": "agent",
                    "description": "second",
                    "output": {"type": "text"},
                },
            ],
            "edges": [{"from": "T1", "to": "T2"}],
        }

        converted = v2_to_v3(v2_graph)

        validate_v3_graph_json(converted)
        t1 = next(node for node in converted["nodes"] if node["id"] == "T1")
        self.assertEqual(t1["taskBoundaries"], ["workspace"])
        self.assertEqual(
            t1["outputContract"]["ports"][0]["jsonSchema"]["type"],
            "object",
        )
        self.assertEqual(t1["taskSpec"]["executor"], "agent")

    def test_migrate_marks_non_runnable_when_source_insufficient(self) -> None:
        converted = legacy_to_v3({"nodes": [{"id": "N1", "type": "agent_task"}], "edges": []})
        node = next(item for item in converted["nodes"] if item["id"] == "N1")
        self.assertFalse(node["taskSpec"]["runnable"])
        self.assertIn("nonRunnableReason", node["taskSpec"])

    def test_invalid_input_fails_with_clear_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "nodes 必須是 list"):
            legacy_to_v3({"nodes": {}, "edges": []})

    def test_cli_batch_mode_converts_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            in_dir = Path(tempdir) / "in"
            out_dir = Path(tempdir) / "out"
            in_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "nodes": [{"id": "N1", "type": "agent_task", "description": "run"}],
                "edges": [],
            }
            (in_dir / "a.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            args = Namespace(in_dir=str(in_dir), out_dir=str(out_dir), format="legacy", input=None, output=None)
            cli._handle_graph_migrate(args)

            generated = out_dir / "a.json"
            self.assertTrue(generated.exists())
            converted = json.loads(generated.read_text(encoding="utf-8"))
            self.assertEqual(converted["version"], "taskgraph.v3")


if __name__ == "__main__":
    unittest.main()
