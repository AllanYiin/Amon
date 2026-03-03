import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.taskgraph.v3.models import SCHEMA_VERSION_V3
from amon.taskgraph.v3.schema import to_json_schema
from amon.taskgraph.v3.validate import detect_graph_version, parse_graph, parse_graph_any


class TaskGraphV3SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example_path = Path(__file__).resolve().parents[1] / "examples" / "graph_v3_minimal.json"
        self.graph_payload = json.loads(self.example_path.read_text(encoding="utf-8"))

    def test_parse_graph_valid_v3(self) -> None:
        graph = parse_graph(self.graph_payload)
        self.assertEqual(graph.schemaVersion, SCHEMA_VERSION_V3)
        self.assertEqual(len(graph.nodes), 2)
        self.assertEqual(graph.edges[0].edgeId, "e1")

    def test_parse_graph_invalid_missing_port_ref(self) -> None:
        payload = json.loads(json.dumps(self.graph_payload))
        payload["edges"][0]["toPort"] = "missing"
        with self.assertRaisesRegex(ValueError, "edge.toPort 不存在"):
            parse_graph(payload)

    def test_parse_graph_invalid_typeref_format(self) -> None:
        payload = json.loads(json.dumps(self.graph_payload))
        payload["nodes"][0]["outputs"][0]["typeRef"] = "enums/Priority"
        with self.assertRaisesRegex(ValueError, "typeRef 格式不合法"):
            parse_graph(payload)

    def test_detect_and_parse_v2(self) -> None:
        v2_payload = {
            "schema_version": "2.0",
            "objective": "sample",
            "session_defaults": {},
            "nodes": [
                {
                    "id": "N1",
                    "title": "a",
                    "kind": "llm",
                    "description": "d",
                    "reads": [],
                    "writes": {},
                    "tools": [],
                    "steps": [],
                    "output": {"type": "text", "extract": "best_effort"},
                    "guardrails": {},
                    "retry": {"max_attempts": 1, "backoff_s": 1, "jitter_s": 0},
                    "timeout": {"inactivity_s": 30, "hard_s": 60},
                }
            ],
            "edges": [],
        }
        self.assertEqual(detect_graph_version(v2_payload), "2.0")
        parsed = parse_graph_any(v2_payload)
        self.assertEqual(parsed.schema_version, "2.0")

    def test_schema_golden(self) -> None:
        golden_path = Path(__file__).resolve().parent / "golden" / "taskgraph" / "taskgraph_v3_schema.json"
        expected = golden_path.read_text(encoding="utf-8")
        actual = json.dumps(to_json_schema(None), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
