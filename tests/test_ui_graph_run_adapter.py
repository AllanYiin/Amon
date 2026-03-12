from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


@unittest.skipIf(shutil.which("node") is None, "node is required for frontend adapter tests")
class TaskGraphV3AdapterTests(unittest.TestCase):
    def _run_adapter_script(self, script: str) -> dict:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return json.loads(completed.stdout)

    def test_maps_runtime_status_priority(self) -> None:
        module_uri = (Path("src/amon/ui/static/js/domain/graphRuntimeAdapter.js").resolve().as_uri())
        script = textwrap.dedent(
          f"""
          import {{ buildGraphRuntimeViewModel }} from "{module_uri}";
          const vm = buildGraphRuntimeViewModel({{
            graphPayload: {{
              graph: {{
                nodes: [
                  {{ id: "n1", status: "pending" }},
                  {{ id: "n2", status: "completed" }},
                  {{ id: "n3", state: "error" }}
                ]
              }}
            }},
            nodeStates: {{
              n1: {{ status: "running" }},
              n2: {{ status: "done" }},
              n3: {{ status: "failed" }}
            }}
          }});
          console.log(JSON.stringify({{
            statuses: vm.nodes.map((item) => item.effectiveStatus),
            labels: vm.nodes.map((item) => item.statusUi.label)
          }}));
          """
        )
        payload = self._run_adapter_script(script)
        self.assertEqual(payload["statuses"], ["running", "succeeded", "failed"])
        self.assertEqual(payload["labels"], ["執行中", "成功", "失敗"])

    def test_missing_node_states_returns_unknown_without_throw(self) -> None:
        module_uri = (Path("src/amon/ui/static/js/domain/graphRuntimeAdapter.js").resolve().as_uri())
        script = textwrap.dedent(
          f"""
          import {{ buildGraphRuntimeViewModel }} from "{module_uri}";
          const vm = buildGraphRuntimeViewModel({{
            graphPayload: {{
              run_id: "run-x",
              graph: {{
                nodes: [
                  {{ id: "n1" }},
                  {{ id: "n2", state: "running" }}
                ]
              }}
            }}
          }});
          console.log(JSON.stringify({{
            diagnostics: vm.diagnostics,
            statuses: vm.nodes.map((item) => item.effectiveStatus)
          }}));
          """
        )
        payload = self._run_adapter_script(script)
        self.assertIn("node_states_missing", payload["diagnostics"])
        self.assertEqual(payload["statuses"], ["unknown", "running"])

    def test_marks_next_runnable_node_and_focus_target(self) -> None:
        module_uri = (Path("src/amon/ui/static/js/domain/graphRuntimeAdapter.js").resolve().as_uri())
        script = textwrap.dedent(
          f"""
          import {{ buildGraphRuntimeViewModel }} from "{module_uri}";
          const vm = buildGraphRuntimeViewModel({{
            graphPayload: {{
              graph: {{
                nodes: [
                  {{ id: "n1", title: "Start" }},
                  {{ id: "n2", title: "Planner" }},
                  {{ id: "n3", title: "Writer" }}
                ],
                edges: [
                  {{ from: "n1", to: "n2", kind: "next", edge_type: "CONTROL" }},
                  {{ from: "n2", to: "n3", kind: "next", edge_type: "CONTROL" }}
                ]
              }}
            }},
            nodeStates: {{
              n1: {{ status: "done" }},
              n2: {{ status: "pending" }},
              n3: {{ status: "pending" }}
            }}
          }});
          console.log(JSON.stringify({{
            preferredFocusNodeId: vm.preferredFocusNodeId,
            nodes: vm.nodes.map((item) => ({{
              id: item.id,
              isNext: item.isNext,
              isBlocked: item.isBlocked,
              level: item.level
            }}))
          }}));
          """
        )
        payload = self._run_adapter_script(script)
        self.assertEqual(payload["preferredFocusNodeId"], "n2")
        self.assertEqual(
            payload["nodes"],
            [
                {"id": "n1", "isNext": False, "isBlocked": False, "level": 0},
                {"id": "n2", "isNext": True, "isBlocked": False, "level": 1},
                {"id": "n3", "isNext": False, "isBlocked": True, "level": 2},
            ],
        )

