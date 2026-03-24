import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.domain import AmonManifest, ExecutorBinding, ManifestProject, TaskDefinition, WorkflowDefinition, WorkflowNode
from amon.planning.binder import BindingError, bind_workflow
from amon.planning.compiler_vnext import CompilerError, compile_manifest_workflow


def _subgraph_manifest() -> AmonManifest:
    return AmonManifest(
        project=ManifestProject(id="project.demo", name="Demo"),
        tasks={
            "task.subgraph": TaskDefinition.create(
                task_id="task.subgraph",
                title="Subgraph task",
                goal="run nested workflow",
                required_capabilities=["graph_orchestration"],
                status="active",
            )
        },
        executors={
            "exec.subgraph": ExecutorBinding.create(
                executor_id="exec.subgraph",
                executor_type="subgraph",
                capabilities=["graph_orchestration"],
                status="active",
            )
        },
        workflows={
            "workflow.demo": WorkflowDefinition.create(
                workflow_id="workflow.demo",
                name="Demo",
                nodes=[
                    WorkflowNode(
                        id="subgraph_step",
                        task_ref="task.subgraph",
                        executor_ref="exec.subgraph",
                        status="valid",
                    )
                ],
                status="valid",
            )
        },
    )


class SubgraphRejectionTests(unittest.TestCase):
    def test_binder_rejects_subgraph_executor_with_stable_code(self) -> None:
        manifest = _subgraph_manifest()
        workflow = manifest.workflows["workflow.demo"].clone()
        workflow.update(status="draft", nodes=[WorkflowNode(id="subgraph_step", task_ref="task.subgraph", executor_ref="exec.subgraph", status="draft")])
        manifest.workflows[workflow.id] = workflow

        with self.assertRaises(BindingError) as ctx:
            bind_workflow(manifest, "workflow.demo")

        self.assertEqual(ctx.exception.code, "AMON_EXECUTOR_TYPE_001")
        self.assertIn("subgraph executor 尚未支援", str(ctx.exception))

    def test_compiler_rejects_subgraph_executor_with_stable_code(self) -> None:
        manifest = _subgraph_manifest()

        with self.assertRaises(CompilerError) as ctx:
            compile_manifest_workflow(manifest, "workflow.demo")

        self.assertEqual(ctx.exception.code, "AMON_EXECUTOR_TYPE_001")
        self.assertIn("subgraph executor 尚未支援", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
