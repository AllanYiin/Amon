from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest, ExecutorBinding, ManifestProject, TaskDefinition, WorkflowDefinition, WorkflowNode
from amon.planning.compiler_vnext import compile_manifest_workflow
from amon.taskgraph3.amon_node_runner import AmonNodeRunner


def _human_gate_manifest() -> AmonManifest:
    return AmonManifest(
        project=ManifestProject(id="project.demo", name="Demo"),
        tasks={
            "task.human_gate": TaskDefinition.create(
                task_id="task.human_gate",
                title="Human gate",
                goal="等待人工確認是否繼續",
                required_capabilities=["approval_gate"],
                status="active",
            )
        },
        executors={
            "exec.human_gate": ExecutorBinding.create(
                executor_id="exec.human_gate",
                executor_type="human_gate",
                capabilities=["approval_gate"],
                status="active",
            )
        },
        workflows={
            "workflow.human_gate": WorkflowDefinition.create(
                workflow_id="workflow.human_gate",
                name="Human Gate Flow",
                nodes=[
                    WorkflowNode(
                        id="approval_step",
                        task_ref="task.human_gate",
                        executor_ref="exec.human_gate",
                        status="valid",
                    )
                ],
                status="valid",
            )
        },
    )


class HumanGateFlowIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_runtime_flag = os.environ.get("AMON_VNEXT_RUNTIME")
        os.environ["AMON_VNEXT_RUNTIME"] = "1"

    def tearDown(self) -> None:
        if self._old_runtime_flag is None:
            os.environ.pop("AMON_VNEXT_RUNTIME", None)
            return
        os.environ["AMON_VNEXT_RUNTIME"] = self._old_runtime_flag

    def test_human_gate_manifest_compiles_and_waits_for_confirmation(self) -> None:
        manifest = _human_gate_manifest()
        graph = compile_manifest_workflow(manifest, "workflow.human_gate").graph
        node = graph.nodes[0]

        self.assertEqual(node.metadata["executor_type"], "human_gate")

        with tempfile.TemporaryDirectory() as tmp:
            events: list[str] = []
            runner = AmonNodeRunner(
                core=SimpleNamespace(),
                project_path=Path(tmp),
                run_id="run-human-gate",
                variables={},
                stream_handler=None,
            )

            original_emit = runner._emit_runtime_event

            def _capture(event: dict[str, object]) -> None:
                events.append(str(event.get("event") or ""))
                original_emit(event)

            runner._emit_runtime_event = _capture  # type: ignore[method-assign]
            result = runner.run_task(node, {})

            self.assertEqual(result["status"], "waiting_confirmation")
            self.assertEqual(events, ["node.confirmation_requested"])
            self.assertTrue((Path(tmp) / ".amon" / "runs" / "run-human-gate" / "confirmations").exists())


if __name__ == "__main__":
    unittest.main()
