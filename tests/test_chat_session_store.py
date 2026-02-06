import json
import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.session_store import append_event, create_chat_session


class ChatSessionStoreTests(unittest.TestCase):
    def test_create_chat_session_and_append_user_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-123"
                chat_id = create_chat_session(project_id)
                append_event(chat_id, {"type": "user", "text": "哈囉", "project_id": project_id})
            finally:
                os.environ.pop("AMON_HOME", None)

            session_path = (
                Path(temp_dir) / "projects" / project_id / "sessions" / "chat" / f"{chat_id}.jsonl"
            )
            self.assertTrue(session_path.exists())
            lines = session_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["type"], "user")
            self.assertEqual(payload["text"], "哈囉")
            self.assertEqual(payload["project_id"], project_id)
            self.assertIn("ts", payload)

    def test_append_assistant_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-456"
                chat_id = create_chat_session(project_id)
                append_event(
                    chat_id,
                    {"type": "assistant_chunk", "text": "第一段", "project_id": project_id},
                )
                append_event(
                    chat_id,
                    {"type": "assistant_chunk", "text": "第二段", "project_id": project_id},
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            session_path = (
                Path(temp_dir) / "projects" / project_id / "sessions" / "chat" / f"{chat_id}.jsonl"
            )
            lines = [line for line in session_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            payloads = [json.loads(line) for line in lines]
            self.assertTrue(all(payload["type"] == "assistant_chunk" for payload in payloads))

    def test_rejects_invalid_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                with self.assertRaises(ValueError):
                    create_chat_session("../escape")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
