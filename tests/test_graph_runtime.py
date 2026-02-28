import json
import os
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.graph_runtime import GraphRuntime
from amon.run.context import append_run_constraints


class GraphRuntimeTests(unittest.TestCase):
    def test_agent_task_stream_updates_inactivity_deadline(self) -> None:
        class _StubCore:
            def __init__(self) -> None:
                self.logger = __import__("logging").getLogger("graph-runtime-test")

            def run_agent_task(self, *_args, stream_handler=None, **_kwargs):
                if stream_handler:
                    for _ in range(4):
                        stream_handler("token")
                        time.sleep(0.35)
                return "ok"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            graph_path = project_path / "graph.json"
            graph_path.write_text(json.dumps({"nodes": [], "edges": []}, ensure_ascii=False), encoding="utf-8")
            events_path = project_path / "events.jsonl"
            runtime = GraphRuntime(core=_StubCore(), project_path=project_path, graph_path=graph_path)
            runtime._inject_run_constraints = lambda prompt, _run_id: prompt  # type: ignore[method-assign]
            node = {
                "id": "agent",
                "type": "agent_task",
                "prompt": "hello",
                "inactivity_timeout_s": 1,
                "hard_timeout_s": 5,
            }
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = runtime._execute_node_with_timeout(
                    node,
                    {},
                    "run-stream",
                    events_path=events_path,
                    executor=executor,
                )

        self.assertEqual(result.get("content"), "ok")

    def test_graph_run_creates_state_and_outputs(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("需要設定 OPENAI_API_KEY 才能執行 LLM 測試")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Graph 專案")
                project_path = Path(project.path)

                graph = {
                    "variables": {"name": "Amon"},
                    "nodes": [
                        {
                            "id": "write",
                            "type": "write_file",
                            "path": "docs/output.txt",
                            "content": "Hello ${name}",
                        },
                        {
                            "id": "agent",
                            "type": "agent_task",
                            "prompt": "Hi ${name}",
                        },
                    ],
                    "edges": [{"from": "write", "to": "agent"}],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                result = core.run_graph(project_path=project_path, graph_path=graph_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            run_dir = result.run_dir
            state_path = run_dir / "state.json"
            resolved_path = run_dir / "graph.resolved.json"
            events_path = run_dir / "events.jsonl"

            self.assertTrue(state_path.exists())
            self.assertTrue(resolved_path.exists())
            self.assertTrue(events_path.exists())

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "completed")
            self.assertIn("write", state["nodes"])
            self.assertIn("agent", state["nodes"])
            self.assertEqual(state["nodes"]["write"]["status"], "completed")
            self.assertEqual(state["nodes"]["agent"]["status"], "completed")

            output_path = project_path / "docs" / "output.txt"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "Hello Amon")


    def test_graph_runtime_events_include_correlation_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Graph 關聯欄位")
                project_path = Path(project.path)
                graph = {
                    "nodes": [
                        {
                            "id": "write",
                            "type": "write_file",
                            "path": "docs/check.txt",
                            "content": "ok",
                        }
                    ],
                    "edges": [],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
                runtime = GraphRuntime(
                    core=core,
                    project_path=project_path,
                    graph_path=graph_path,
                    run_id="run-correlation",
                    request_id="req-correlation",
                )
                result = runtime.run()
            finally:
                os.environ.pop("AMON_HOME", None)

            events_path = result.run_dir / "events.jsonl"
            events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertGreaterEqual(len(events), 2)
            for item in events:
                for key in ("project_id", "run_id", "node_id", "event_id", "request_id", "tool"):
                    self.assertIn(key, item)
                self.assertEqual(item["project_id"], project.project_id)
                self.assertEqual(item["run_id"], "run-correlation")
                self.assertEqual(item["request_id"], "req-correlation")

    def test_core_run_graph_uses_legacy_runtime_when_schema_version_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Legacy Graph 專案")
                project_path = Path(project.path)
                graph = {
                    "nodes": [
                        {
                            "id": "write",
                            "type": "write_file",
                            "path": "docs/legacy.txt",
                            "content": "legacy",
                        }
                    ],
                    "edges": [],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                result = core.run_graph(project_path=project_path, graph_path=graph_path)
            finally:
                os.environ.pop("AMON_HOME", None)

            output_path = project_path / "docs" / "legacy.txt"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "legacy")
            self.assertEqual(result.state["status"], "completed")

    def test_graph_template_parametrize_and_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Template 專案")
                project_path = Path(project.path)

                graph = {
                    "schema_version": "2.0",
                    "variables": {},
                    "nodes": [
                        {
                            "id": "write",
                            "type": "write_file",
                            "path": "docs/output.txt",
                            "content": "Tesla",
                        }
                    ],
                    "edges": [],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                run_result = core.run_graph(project_path=project_path, graph_path=graph_path)
                template_result = core.create_graph_template(project.project_id, run_result.run_id)
                core.parametrize_graph_template(
                    template_result["template_id"],
                    "$.nodes[0].content",
                    "company",
                )
                template_path = Path(template_result["path"])
                template_payload = json.loads(template_path.read_text(encoding="utf-8"))
                schema_payload = json.loads(Path(template_result["schema_path"]).read_text(encoding="utf-8"))
                variables_schema = template_payload.get("variables_schema", {})
                self.assertIn("company", schema_payload.get("properties", {}))
                self.assertIn("company", variables_schema.get("properties", {}))
                self.assertIn("company", variables_schema.get("required", []))

                template_run = core.run_graph_template(
                    template_result["template_id"],
                    {"company": "Amon"},
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            output_path = project_path / "docs" / "output.txt"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "Amon")
            self.assertNotEqual(run_result.run_id, template_run.run_id)

    def test_graph_template_parametrize_prompt_and_run(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("需要設定 OPENAI_API_KEY 才能執行 LLM 測試")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Prompt 範本專案")
                project_path = Path(project.path)

                graph = {
                    "variables": {},
                    "nodes": [
                        {
                            "id": "agent",
                            "type": "agent_task",
                            "prompt": "原始訊息",
                        }
                    ],
                    "edges": [],
                }
                graph_path = project_path / "graph.json"
                graph_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

                run_result = core.run_graph(project_path=project_path, graph_path=graph_path)
                template_result = core.create_graph_template(project.project_id, run_result.run_id)
                core.parametrize_graph_template(
                    template_result["template_id"],
                    "$.nodes[0].prompt",
                    "user_prompt",
                )

                template_run = core.run_graph_template(
                    template_result["template_id"],
                    {"user_prompt": "替換訊息"},
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            resolved_path = template_run.run_dir / "graph.resolved.json"
            self.assertTrue(resolved_path.exists())
            resolved_payload = json.loads(resolved_path.read_text(encoding="utf-8"))
            self.assertEqual(resolved_payload["nodes"][0]["prompt"], "替換訊息")

    def test_graph_runtime_injects_run_constraints(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("需要設定 OPENAI_API_KEY 才能執行 LLM 測試")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Run Context 專案")
                project_path = Path(project.path)

                run_id = "run-context-test"
                run_dir = project_path / ".amon" / "runs" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                append_run_constraints(run_id, ["用繁體中文", "不要用付費"])

                graph_path = project_path / "graph.json"
                graph_path.write_text("{}", encoding="utf-8")
                runtime = GraphRuntime(core=core, project_path=project_path, graph_path=graph_path)
                runtime._execute_node(
                    {"id": "agent", "type": "agent_task", "prompt": "你好"},
                    {},
                    run_id,
                    cancel_event=threading.Event(),
                    timeout_s=60,
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            sessions_dir = project_path / "sessions"
            session_files = list(sessions_dir.glob("*.jsonl"))
            self.assertEqual(len(session_files), 1)
            session_payloads = [
                json.loads(line)
                for line in session_files[0].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            prompt_events = [payload for payload in session_payloads if payload.get("event") == "prompt"]
            self.assertEqual(len(prompt_events), 1)
            content = prompt_events[0].get("content", "")
            self.assertIn("```run_constraints", content)
            self.assertIn("用繁體中文", content)
            self.assertIn("不要用付費", content)

    def test_graph_runtime_concurrent_runs_with_slow_tool(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Graph 工具專案")
                project_path = Path(project.path)

                tools_dir = Path(temp_dir) / "tools"
                tools_dir.mkdir(parents=True, exist_ok=True)
                config_path = Path(temp_dir) / "config.yaml"
                config_path.write_text(
                    json.dumps({"tools": {"global_dir": str(tools_dir)}}, ensure_ascii=False),
                    encoding="utf-8",
                )

                sleeper_dir = tools_dir / "sleeper"
                sleeper_dir.mkdir(parents=True, exist_ok=True)
                (sleeper_dir / "tool.py").write_text(
                    "\n".join(
                        [
                            "import json",
                            "import sys",
                            "import time",
                            "payload = json.loads(sys.stdin.read() or \"{}\")",
                            "time.sleep(float(payload.get(\"sleep_s\", 2)))",
                            "print(json.dumps({\"ok\": True}))",
                        ]
                    ),
                    encoding="utf-8",
                )
                (sleeper_dir / "tool.yaml").write_text(
                    json.dumps(
                        {
                            "name": "sleeper",
                            "version": "0.1.0",
                            "inputs_schema": {"type": "object"},
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                fast_dir = tools_dir / "fast"
                fast_dir.mkdir(parents=True, exist_ok=True)
                (fast_dir / "tool.py").write_text(
                    "\n".join(
                        [
                            "import json",
                            "import sys",
                            "json.loads(sys.stdin.read() or \"{}\")",
                            "print(json.dumps({\"ok\": True}))",
                        ]
                    ),
                    encoding="utf-8",
                )
                (fast_dir / "tool.yaml").write_text(
                    json.dumps(
                        {
                            "name": "fast",
                            "version": "0.1.0",
                            "inputs_schema": {"type": "object"},
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                slow_graph = {
                    "schema_version": "2.0",
                    "nodes": [
                        {
                            "id": "slow",
                            "type": "tool.call",
                            "tool": "sleeper",
                            "args": {"sleep_s": 2},
                            "timeout_s": 10,
                        }
                    ],
                    "edges": [],
                }
                fast_graph = {
                    "schema_version": "2.0",
                    "nodes": [
                        {
                            "id": "fast",
                            "type": "tool.call",
                            "tool": "fast",
                            "args": {},
                            "timeout_s": 5,
                        }
                    ],
                    "edges": [],
                }
                slow_graph_path = project_path / "graph_slow.json"
                slow_graph_path.write_text(json.dumps(slow_graph, ensure_ascii=False), encoding="utf-8")
                fast_graph_path = project_path / "graph_fast.json"
                fast_graph_path.write_text(json.dumps(fast_graph, ensure_ascii=False), encoding="utf-8")

                slow_runtime = GraphRuntime(
                    core=core,
                    project_path=project_path,
                    graph_path=slow_graph_path,
                    run_id="slow-run",
                )
                slow_thread = threading.Thread(target=slow_runtime.run, daemon=True)
                slow_thread.start()

                slow_events = project_path / ".amon" / "runs" / "slow-run" / "events.jsonl"
                start_wait = time.monotonic()
                while not slow_events.exists() and (time.monotonic() - start_wait) < 2:
                    time.sleep(0.05)

                fast_start = time.monotonic()
                core.run_graph(project_path=project_path, graph_path=fast_graph_path, run_id="fast-run")
                fast_elapsed = time.monotonic() - fast_start
                self.assertLess(fast_elapsed, 2)
                self.assertTrue(slow_thread.is_alive())
                slow_thread.join(timeout=5)
                self.assertFalse(slow_thread.is_alive())
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
