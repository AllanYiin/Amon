from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


@unittest.skipIf(shutil.which("node") is None, "node is required for frontend adapter tests")
class GraphRuntimeAdapterTests(unittest.TestCase):
    def _run_adapter_script(self, script: str) -> dict:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
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

