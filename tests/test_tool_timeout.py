import os
import tempfile
import time
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from amon.daemon.queue import configure_action_queue, enqueue_action


class ToolTimeoutTests(unittest.TestCase):
    def test_tool_timeout_does_not_block_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                tools_dir = Path(temp_dir) / "tools"
                tools_dir.mkdir(parents=True, exist_ok=True)
                config_path = Path(temp_dir) / "config.yaml"
                config_path.write_text(
                    yaml.safe_dump({"tools": {"global_dir": str(tools_dir)}}),
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
                            "time.sleep(120)",
                            "print(json.dumps({\"ok\": True, \"payload\": payload}))",
                        ]
                    ),
                    encoding="utf-8",
                )
                (sleeper_dir / "tool.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "name": "sleeper",
                            "version": "0.1.0",
                            "inputs_schema": {"type": "object"},
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        }
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
                            "payload = json.loads(sys.stdin.read() or \"{}\")",
                            "print(json.dumps({\"ok\": True, \"payload\": payload}))",
                        ]
                    ),
                    encoding="utf-8",
                )
                (fast_dir / "tool.yaml").write_text(
                    yaml.safe_dump(
                        {
                            "name": "fast",
                            "version": "0.1.0",
                            "inputs_schema": {"type": "object"},
                            "outputs_schema": {"type": "object"},
                            "risk_level": "low",
                            "allowed_paths": [],
                        }
                    ),
                    encoding="utf-8",
                )

                action_queue = configure_action_queue(data_dir=Path(temp_dir), worker_count=2)
                try:
                    start = time.monotonic()
                    enqueue_action(
                        {
                            "hook_id": "hook-sleeper",
                            "action_type": "tool.call",
                            "tool": "sleeper",
                            "action_args": {"note": "sleep"},
                            "event": {"event_id": "evt-sleep"},
                            "timeout_s": 1,
                        }
                    )
                    enqueue_action(
                        {
                            "hook_id": "hook-fast",
                            "action_type": "tool.call",
                            "tool": "fast",
                            "action_args": {"note": "fast"},
                            "event": {"event_id": "evt-fast"},
                            "timeout_s": 5,
                        }
                    )
                    self.assertTrue(action_queue.wait_for_idle(timeout=6))
                    elapsed = time.monotonic() - start
                    self.assertLess(elapsed, 6)
                finally:
                    action_queue.stop()
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
