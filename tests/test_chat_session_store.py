import json
import os
import tempfile
import unittest
from pathlib import Path

import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.session_store import (
    NOISY_EVENT_TYPES,
    append_event,
    build_prompt_with_history,
    create_chat_session,
    ensure_chat_session,
    chat_session_exists,
    load_latest_chat_id,
    load_latest_run_context,
    load_recent_dialogue,
)


class ChatSessionStoreTests(unittest.TestCase):
    def test_assistant_chunk_does_not_emit_chat_session_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-log-001"
                chat_id = create_chat_session(project_id)
                with patch("amon.chat.session_store.log_event") as mock_log_event:
                    append_event(
                        chat_id,
                        {"type": "assistant_chunk", "text": "第一段", "project_id": project_id},
                    )
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertIn("assistant_chunk", NOISY_EVENT_TYPES)
        self.assertFalse(
            any(
                isinstance(call.args[0], dict)
                and call.args[0].get("event") == "chat_session_event"
                for call in mock_log_event.call_args_list
            )
        )

    def test_user_event_still_emits_chat_session_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-log-002"
                chat_id = create_chat_session(project_id)
                with patch("amon.chat.session_store.log_event") as mock_log_event:
                    append_event(chat_id, {"type": "user", "text": "哈囉", "project_id": project_id})
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertTrue(
            any(
                isinstance(call.args[0], dict)
                and call.args[0].get("event") == "chat_session_event"
                and call.args[0].get("type") == "user"
                for call in mock_log_event.call_args_list
            )
        )

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


    def test_ensure_chat_session_prefers_incoming_then_latest_then_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-ensure-session"
                created_chat_id, created_source = ensure_chat_session(project_id)
                self.assertEqual(created_source, "new")
                self.assertTrue(chat_session_exists(project_id, created_chat_id))

                ensured_chat_id, ensured_source = ensure_chat_session(project_id, created_chat_id)
                self.assertEqual(ensured_source, "incoming")
                self.assertEqual(ensured_chat_id, created_chat_id)

                latest_chat_id, latest_source = ensure_chat_session(project_id, "missing-chat")
                self.assertEqual(latest_source, "latest")
                self.assertEqual(latest_chat_id, created_chat_id)
                self.assertEqual(load_latest_chat_id(project_id), created_chat_id)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_load_recent_dialogue_filters_non_dialogue_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-789"
                chat_id = create_chat_session(project_id)
                append_event(chat_id, {"type": "user", "text": "你好", "project_id": project_id})
                append_event(chat_id, {"type": "router", "text": "chat_response", "project_id": project_id})
                append_event(chat_id, {"type": "assistant", "text": "哈囉！", "project_id": project_id})
                append_event(chat_id, {"type": "assistant_chunk", "text": "ignored", "project_id": project_id})
                dialogue = load_recent_dialogue(project_id, chat_id)
            finally:
                os.environ.pop("AMON_HOME", None)

            self.assertEqual(
                dialogue,
                [
                    {"role": "user", "content": "你好"},
                    {"role": "assistant", "content": "哈囉！"},
                ],
            )

    def test_build_prompt_with_history_includes_previous_turns(self) -> None:
        prompt = build_prompt_with_history(
            "請繼續",
            [
                {"role": "user", "content": "幫我整理簡報"},
                {"role": "assistant", "content": "好的，請提供主題。"},
            ],
        )
        self.assertIn("[核心任務]", prompt)
        self.assertIn("幫我整理簡報", prompt)
        self.assertIn("[歷史對話]", prompt)
        self.assertIn("使用者: 幫我整理簡報", prompt)
        self.assertIn("Amon: 好的，請提供主題。", prompt)
        self.assertIn("[目前訊息]", prompt)
        self.assertIn("使用者: 請繼續", prompt)
        self.assertIn("請直接沿用既有任務往下執行", prompt)
        self.assertIn("除非缺少關鍵資訊而無法完成任務", prompt)
        self.assertIn("不要用問句收尾", prompt)

    def test_build_prompt_with_history_trims_long_assistant_turn(self) -> None:
        long_assistant = "A" * 1200
        prompt = build_prompt_with_history(
            "不用，桌面版即可",
            [
                {"role": "user", "content": "請協助我開發一個俄羅斯方塊單頁網頁應用程式"},
                {"role": "assistant", "content": long_assistant},
            ],
        )

        self.assertIn("[核心任務]", prompt)
        self.assertIn("俄羅斯方塊單頁網頁應用程式", prompt)
        self.assertIn("Amon: " + ("A" * 200), prompt)
        self.assertNotIn("A" * 1000, prompt)

    def test_load_latest_run_context_tracks_run_and_last_assistant(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-run-ctx"
                chat_id = create_chat_session(project_id)
                append_event(chat_id, {"type": "user", "text": "先幫我規劃", "project_id": project_id})
                append_event(
                    chat_id,
                    {
                        "type": "assistant",
                        "text": "好的，請問你想先做 UI 還是 API？",
                        "project_id": project_id,
                        "run_id": "run-123",
                    },
                )
                context = load_latest_run_context(project_id, chat_id)
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertEqual(context["run_id"], "run-123")
        self.assertEqual(context["last_assistant_text"], "好的，請問你想先做 UI 還是 API？")

    def test_rejects_invalid_chat_id_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                with self.assertRaises(ValueError):
                    append_event("../evil", {"type": "user", "text": "hi", "project_id": "proj-safe-001"})
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_load_recent_dialogue_reads_tail_with_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-tail-001"
                chat_id = create_chat_session(project_id)
                for idx in range(80):
                    append_event(chat_id, {"type": "user", "text": f"u{idx}", "project_id": project_id})
                    append_event(chat_id, {"type": "assistant", "text": f"a{idx}", "project_id": project_id})
                dialogue = load_recent_dialogue(project_id, chat_id, limit=4)
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertEqual(
            dialogue,
            [
                {"role": "user", "content": "u78"},
                {"role": "assistant", "content": "a78"},
                {"role": "user", "content": "u79"},
                {"role": "assistant", "content": "a79"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
