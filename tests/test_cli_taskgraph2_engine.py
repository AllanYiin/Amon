import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon import cli
from amon.core import AmonCore


class _FakeLLMClient:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)

    def generate_stream(self, messages: list[dict[str, str]], model=None):  # noqa: ANN001
        output = self._outputs.pop(0)
        for token in output.split(" "):
            if token:
                yield token + " "


class CliTaskGraph2EngineTests(unittest.TestCase):
    def test_parser_supports_run_chat_engine_option(self) -> None:
        parser = cli.build_parser()

        run_args = parser.parse_args(["run", "任務", "--project", "p1", "--engine", "taskgraph2"])
        self.assertEqual(run_args.engine, "taskgraph2")

        chat_args = parser.parse_args(["chat", "--project", "p1", "--engine", "taskgraph2"])
        self.assertEqual(chat_args.engine, "taskgraph2")

        default_args = parser.parse_args(["run", "任務", "--project", "p1"])
        self.assertEqual(default_args.engine, "taskgraph2")

    def test_handle_run_taskgraph2_delegates_to_core(self) -> None:
        core = Mock()
        core.get_project_path.return_value = Path("/tmp/project")
        args = argparse.Namespace(
            user_task="整理需求",
            prompt=None,
            project="project-1",
            model="gpt-test",
            mode="single",
            skill=["demo"],
            engine="taskgraph2",
        )

        cli._handle_run(core, args)

        core.run_taskgraph2.assert_called_once_with(
            "整理需求",
            project_path=Path("/tmp/project"),
            project_id="project-1",
            model="gpt-test",
            skill_names=["demo"],
        )


    def test_handle_run_v1_option_is_forced_to_taskgraph2(self) -> None:
        core = Mock()
        core.get_project_path.return_value = Path("/tmp/project")
        args = argparse.Namespace(
            user_task="整理需求",
            prompt=None,
            project="project-1",
            model=None,
            mode="single",
            skill=[],
            engine="v1",
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            cli._handle_run(core, args)

        self.assertIn("v1 已停用", stdout.getvalue())
        core.run_taskgraph2.assert_called_once()

    def test_graph_run_schema_v2_uses_taskgraph_runtime_and_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                project = core.create_project("測試專案")
                project_path = core.get_project_path(project.project_id)
                graph_path = project_path / "graph-v2.json"
                graph_payload = {
                    "schema_version": "2.0",
                    "objective": "最小整合測試",
                    "session_defaults": {"topic": "integration"},
                    "nodes": [
                        {
                            "id": "N1",
                            "title": "step1",
                            "kind": "task",
                            "description": "第一步",
                            "reads": ["topic"],
                            "writes": {"draft": "text"},
                        },
                        {
                            "id": "N2",
                            "title": "step2",
                            "kind": "task",
                            "description": "第二步",
                            "reads": ["draft"],
                            "writes": {"final": "text"},
                        },
                    ],
                    "edges": [{"from": "N1", "to": "N2"}],
                }
                graph_path.write_text(json.dumps(graph_payload, ensure_ascii=False), encoding="utf-8")

                args = argparse.Namespace(
                    graph_command="run",
                    template=None,
                    var=[],
                    project=project.project_id,
                    graph=str(graph_path),
                )

                with patch("amon.taskgraph2.runtime.build_default_llm_client", return_value=_FakeLLMClient(["第一步", "第二步"])):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        cli._handle_graph(core, args)

                output = stdout.getvalue()
                self.assertIn("已完成 graph 執行", output)
                run_id = output.split("已完成 graph 執行：", 1)[1].splitlines()[0].strip()
                run_dir = project_path / ".amon" / "runs" / run_id
                self.assertTrue((run_dir / "state.json").exists())
                self.assertTrue((run_dir / "events.jsonl").exists())
                state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
                self.assertEqual(state["status"], "completed")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
