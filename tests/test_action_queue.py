import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.daemon.queue import configure_action_queue, enqueue_action


class ActionQueueTests(unittest.TestCase):
    def test_bulk_enqueue_is_non_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                completed = 0
                lock = threading.Lock()

                def fake_executor(tool_name: str, args: dict[str, object], project_id: str | None) -> dict[str, object]:
                    nonlocal completed
                    time.sleep(0.001)
                    with lock:
                        completed += 1
                    return {"ok": True}

                action_queue = configure_action_queue(tool_executor=fake_executor, data_dir=Path(temp_dir))
                try:
                    start = time.monotonic()
                    for index in range(1000):
                        enqueue_action(
                            {
                                "hook_id": "bulk-hook",
                                "action_type": "tool.call",
                                "tool": "bulk",
                                "action_args": {"index": index},
                                "event": {"event_id": f"evt-{index}"},
                            }
                        )
                    enqueue_duration = time.monotonic() - start
                    self.assertLess(enqueue_duration, 1.0)
                    self.assertTrue(action_queue.wait_for_idle(timeout=10))
                    with lock:
                        self.assertEqual(completed, 1000)
                finally:
                    action_queue.stop()
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
