import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from amon.core import AmonCore
from amon.daemon.queue import configure_action_queue
from amon.hooks.runner import process_event
from amon.storage import RunRepository


class HookToRunIntegrationTests(unittest.TestCase):
    def test_hook_run_request_creates_queued_run_with_trigger_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Trigger Hook")
                hooks_dir = Path(temp_dir) / "hooks"
                hooks_dir.mkdir(parents=True, exist_ok=True)
                (hooks_dir / "run_hook.yaml").write_text(
                    "\n".join(
                        [
                            "event_types:",
                            "  - file.created",
                            "action:",
                            "  type: run.request",
                            "  args:",
                            f"    project_id: \"{project.project_id}\"",
                            "    template_ref: \"single\"",
                            "    variables:",
                            "      source_path: \"{{event.payload.path}}\"",
                        ]
                    ),
                    encoding="utf-8",
                )

                queue = configure_action_queue(data_dir=Path(temp_dir))
                try:
                    results = process_event(
                        {
                            "event_id": "evt-hook-1",
                            "type": "file.created",
                            "scope": "project",
                            "project_id": project.project_id,
                            "actor": "user",
                            "payload": {"path": "docs/spec.md"},
                            "risk": "low",
                        },
                        data_dir=Path(temp_dir),
                        now=datetime.now(timezone.utc),
                    )
                    queue.wait_for_idle(timeout=10)
                finally:
                    queue.stop()

                self.assertEqual(results[0]["status"], "queued")
                run_repo = RunRepository(core.get_project_path(project.project_id))
                runs = run_repo.list()
                self.assertEqual(len(runs), 1)
                self.assertEqual(runs[0].status, "queued")
                self.assertEqual(runs[0].template_ref, "single")
                self.assertEqual(runs[0].trigger["kind"], "hook")
                self.assertEqual(runs[0].trigger["id"], "run_hook")
                self.assertEqual(runs[0].trigger["event_id"], "evt-hook-1")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
