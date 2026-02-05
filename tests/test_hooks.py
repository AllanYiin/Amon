import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from amon.hooks.runner import process_event


class HookRunnerTests(unittest.TestCase):
    def test_event_triggers_tool_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                hooks_dir = Path(temp_dir) / "hooks"
                hooks_dir.mkdir(parents=True, exist_ok=True)
                (hooks_dir / "file_hook.yaml").write_text(
                    "\n".join(
                        [
                            "event_types:",
                            "  - file.created",
                            "filter:",
                            "  path_glob: \"**/*.txt\"",
                            "  min_size: 5",
                            "  mime: \"text/plain\"",
                            "  ignore_actors:",
                            "    - bot",
                            "action:",
                            "  type: tool.call",
                            "  tool: echoer",
                            "  args:",
                            "    path: \"{{event.payload.path}}\"",
                            "    size: \"{{event.payload.size}}\"",
                        ]
                    ),
                    encoding="utf-8",
                )

                calls: list[tuple[str, dict[str, object], str | None]] = []

                def fake_executor(tool_name: str, args: dict[str, object], project_id: str | None) -> dict[str, object]:
                    calls.append((tool_name, args, project_id))
                    return {"ok": True}

                event = {
                    "event_id": "evt-1",
                    "type": "file.created",
                    "scope": "project",
                    "project_id": "proj-1",
                    "actor": "user",
                    "payload": {"path": "docs/readme.txt", "size": 12, "mime": "text/plain"},
                    "risk": "low",
                }

                results = process_event(event, tool_executor=fake_executor, now=datetime.now(timezone.utc))
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["status"], "executed")
                self.assertEqual(len(calls), 1)
                tool_name, args, project_id = calls[0]
                self.assertEqual(tool_name, "echoer")
                self.assertEqual(project_id, "proj-1")
                self.assertEqual(args["path"], "docs/readme.txt")
                self.assertEqual(args["size"], "12")
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_cooldown_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                hooks_dir = Path(temp_dir) / "hooks"
                hooks_dir.mkdir(parents=True, exist_ok=True)
                (hooks_dir / "dedupe_hook.yaml").write_text(
                    "\n".join(
                        [
                            "event_types:",
                            "  - file.created",
                            "dedupe_key: \"{{event.payload.path}}\"",
                            "cooldown_seconds: 300",
                            "action:",
                            "  type: tool.call",
                            "  tool: echoer",
                            "  args:",
                            "    path: \"{{event.payload.path}}\"",
                        ]
                    ),
                    encoding="utf-8",
                )

                calls: list[tuple[str, dict[str, object], str | None]] = []

                def fake_executor(tool_name: str, args: dict[str, object], project_id: str | None) -> dict[str, object]:
                    calls.append((tool_name, args, project_id))
                    return {"ok": True}

                event = {
                    "event_id": "evt-2",
                    "type": "file.created",
                    "scope": "project",
                    "project_id": "proj-1",
                    "actor": "user",
                    "payload": {"path": "docs/readme.txt", "size": 12, "mime": "text/plain"},
                    "risk": "low",
                }

                start = datetime(2024, 1, 1, tzinfo=timezone.utc)
                process_event(event, tool_executor=fake_executor, now=start)
                process_event(event, tool_executor=fake_executor, now=start + timedelta(seconds=100))
                self.assertEqual(len(calls), 1)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_tool_args_validation_blocks_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                tools_root = Path(temp_dir) / "tools"
                tools_dir = tools_root / "validator"
                tools_dir.mkdir(parents=True, exist_ok=True)
                (tools_dir / "tool.py").write_text("# stub", encoding="utf-8")
                (tools_dir / "tool.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "name": "validator",
                            "version": "0.1.0",
                            "inputs_schema": {
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"],
                            },
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        }
                    ),
                    encoding="utf-8",
                )
                config_path = Path(temp_dir) / "config.yaml"
                config_path.write_text(
                    yaml.safe_dump({"tools": {"global_dir": str(tools_root)}}),
                    encoding="utf-8",
                )
                hooks_dir = Path(temp_dir) / "hooks"
                hooks_dir.mkdir(parents=True, exist_ok=True)
                (hooks_dir / "validation_hook.yaml").write_text(
                    "\n".join(
                        [
                            "event_types:",
                            "  - doc.created",
                            "action:",
                            "  type: tool.call",
                            "  tool: validator",
                            "  args:",
                            "    other: \"{{event.payload.other}}\"",
                        ]
                    ),
                    encoding="utf-8",
                )

                calls: list[tuple[str, dict[str, object], str | None]] = []

                def fake_executor(tool_name: str, args: dict[str, object], project_id: str | None) -> dict[str, object]:
                    calls.append((tool_name, args, project_id))
                    return {"ok": True}

                event = {
                    "event_id": "evt-3",
                    "type": "doc.created",
                    "scope": "job",
                    "project_id": None,
                    "actor": "system",
                    "payload": {"other": "value"},
                    "risk": "low",
                }

                results = process_event(event, tool_executor=fake_executor, now=datetime.now(timezone.utc))
                self.assertEqual(results[0]["status"], "failed")
                self.assertEqual(len(calls), 0)
                events_path = Path(temp_dir) / "events" / "events.jsonl"
                lines = events_path.read_text(encoding="utf-8").splitlines()
                validation_events = [json.loads(line) for line in lines if json.loads(line).get("type") == "tool.validation_failed"]
                self.assertEqual(len(validation_events), 1)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_tool_args_validation_allows_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                tools_root = Path(temp_dir) / "tools"
                tools_dir = tools_root / "validator"
                tools_dir.mkdir(parents=True, exist_ok=True)
                (tools_dir / "tool.py").write_text("# stub", encoding="utf-8")
                (tools_dir / "tool.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "name": "validator",
                            "version": "0.1.0",
                            "inputs_schema": {
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"],
                            },
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        }
                    ),
                    encoding="utf-8",
                )
                config_path = Path(temp_dir) / "config.yaml"
                config_path.write_text(
                    yaml.safe_dump({"tools": {"global_dir": str(tools_root)}}),
                    encoding="utf-8",
                )
                hooks_dir = Path(temp_dir) / "hooks"
                hooks_dir.mkdir(parents=True, exist_ok=True)
                (hooks_dir / "validation_hook.yaml").write_text(
                    "\n".join(
                        [
                            "event_types:",
                            "  - doc.created",
                            "action:",
                            "  type: tool.call",
                            "  tool: validator",
                            "  args:",
                            "    text: \"{{event.payload.text}}\"",
                        ]
                    ),
                    encoding="utf-8",
                )

                calls: list[tuple[str, dict[str, object], str | None]] = []

                def fake_executor(tool_name: str, args: dict[str, object], project_id: str | None) -> dict[str, object]:
                    calls.append((tool_name, args, project_id))
                    return {"ok": True}

                event = {
                    "event_id": "evt-4",
                    "type": "doc.created",
                    "scope": "job",
                    "project_id": None,
                    "actor": "system",
                    "payload": {"text": "hello"},
                    "risk": "low",
                }

                results = process_event(event, tool_executor=fake_executor, now=datetime.now(timezone.utc))
                self.assertEqual(results[0]["status"], "executed")
                self.assertEqual(len(calls), 1)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
