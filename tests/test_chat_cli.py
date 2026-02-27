import json
import os
import tempfile
import unittest
from pathlib import Path

import sys
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.cli import run_chat_repl
from amon.core import AmonCore


class ChatCliTests(unittest.TestCase):
    def test_chat_repl_writes_plan_and_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore(data_dir=Path(temp_dir))
                record = core.create_project("測試專案")
                input_iter = iter(["/projects list", "exit"])
                input_func = Mock(side_effect=lambda prompt="": next(input_iter))
                output_func = Mock()

                chat_id = run_chat_repl(core, record.project_id, input_func=input_func, output_func=output_func)
            finally:
                os.environ.pop("AMON_HOME", None)

            session_path = Path(record.path) / "sessions" / "chat" / f"{chat_id}.jsonl"
            self.assertTrue(session_path.exists())
            payloads = [
                json.loads(line)
                for line in session_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            types = {payload["type"] for payload in payloads}
            self.assertIn("plan_created", types)
            self.assertIn("plan_executed", types)


if __name__ == "__main__":
    unittest.main()
