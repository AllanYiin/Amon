import json
import os
import tempfile
import unittest
from pathlib import Path

import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.thread_store import (
    NOISY_EVENT_TYPES,
    append_event,
    build_prompt_with_history,
    create_thread_session,
    ensure_thread_session,
    thread_session_exists,
    load_latest_thread_id,
    load_latest_run_context,
    load_recent_dialogue,
)


class ThreadSessionStoreTests(unittest.TestCase):
    def test_assistant_chunk_does_not_emit_thread_session_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-log-001"
                thread_id = create_thread_session(project_id)
                with patch("amon.chat.thread_store.log_event") as mock_log_event:
                    append_event(
                        thread_id,
                        {"type": "assistant_chunk", "text": "第一段", "project_id": project_id},
                    )
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertIn("assistant_chunk", NOISY_EVENT_TYPES)
        self.assertFalse(
            any(
                isinstance(call.args[0], dict)
                and call.args[0].get("event") == "thread_session_event"
                for call in mock_log_event.call_args_list
            )
        )

    def test_assistant_reasoning_does_not_emit_thread_session_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-log-001b"
                thread_id = create_thread_session(project_id)
                with patch("amon.chat.thread_store.log_event") as mock_log_event:
                    append_event(
                        thread_id,
                        {"type": "assistant_reasoning", "text": "思考中", "project_id": project_id},
                    )
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertIn("assistant_reasoning", NOISY_EVENT_TYPES)
        self.assertFalse(
            any(
                isinstance(call.args[0], dict)
                and call.args[0].get("event") == "thread_session_event"
                for call in mock_log_event.call_args_list
            )
        )

    def test_user_event_still_emits_thread_session_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-log-002"
                thread_id = create_thread_session(project_id)
                with patch("amon.chat.thread_store.log_event") as mock_log_event:
                    append_event(thread_id, {"type": "user", "text": "哈囉", "project_id": project_id})
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertTrue(
            any(
                isinstance(call.args[0], dict)
                and call.args[0].get("event") == "thread_session_event"
                and call.args[0].get("type") == "user"
                for call in mock_log_event.call_args_list
            )
        )

    def test_thread_session_event_log_contains_non_sensitive_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-log-003"
                thread_id = create_thread_session(project_id)
                with patch("amon.chat.thread_store.log_event") as mock_log_event:
                    append_event(
                        thread_id,
                        {
                            "type": "command_result",
                            "text": json.dumps({"status": "confirm_required", "token": "secret-value"}, ensure_ascii=False),
                            "project_id": project_id,
                            "command": "projects_create",
                        },
                    )
            finally:
                os.environ.pop("AMON_HOME", None)

        chat_logs = [
            call.args[0]
            for call in mock_log_event.call_args_list
            if isinstance(call.args[0], dict) and call.args[0].get("event") == "thread_session_event"
        ]
        self.assertEqual(len(chat_logs), 1)
        payload = chat_logs[0]
        self.assertEqual(payload.get("summary"), "command_result:confirm_required")
        self.assertEqual(payload.get("command"), "projects_create")
        expected_chars = len(json.dumps({"status": "confirm_required", "token": "secret-value"}, ensure_ascii=False).strip())
        self.assertEqual(payload.get("text_chars"), expected_chars)
        self.assertNotIn("text", payload)

    def test_create_thread_session_and_append_user_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-123"
                thread_id = create_thread_session(project_id)
                append_event(thread_id, {"type": "user", "text": "哈囉", "project_id": project_id})
            finally:
                os.environ.pop("AMON_HOME", None)

            session_path = (
                Path(temp_dir) / "projects" / project_id / ".amon" / "threads" / thread_id / "events.jsonl"
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
                thread_id = create_thread_session(project_id)
                append_event(
                    thread_id,
                    {"type": "assistant_chunk", "text": "第一段", "project_id": project_id},
                )
                append_event(
                    thread_id,
                    {"type": "assistant_chunk", "text": "第二段", "project_id": project_id},
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            session_path = (
                Path(temp_dir) / "projects" / project_id / ".amon" / "threads" / thread_id / "events.jsonl"
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
                    create_thread_session("../escape")
            finally:
                os.environ.pop("AMON_HOME", None)


    def test_ensure_thread_session_prefers_incoming_then_active_then_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-ensure-session"
                created_thread_id, created_source = ensure_thread_session(project_id)
                self.assertEqual(created_source, "new")
                self.assertTrue(thread_session_exists(project_id, created_thread_id))

                ensured_thread_id, ensured_source = ensure_thread_session(project_id, created_thread_id)
                self.assertEqual(ensured_source, "incoming")
                self.assertEqual(ensured_thread_id, created_thread_id)

                active_thread_id, active_source = ensure_thread_session(project_id, "missing-chat")
                self.assertEqual(active_source, "active")
                self.assertEqual(active_thread_id, created_thread_id)
                self.assertEqual(load_latest_thread_id(project_id), created_thread_id)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_load_recent_dialogue_filters_non_dialogue_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-789"
                thread_id = create_thread_session(project_id)
                append_event(thread_id, {"type": "user", "text": "你好", "project_id": project_id})
                append_event(thread_id, {"type": "router", "text": "chat_response", "project_id": project_id})
                append_event(thread_id, {"type": "assistant", "text": "哈囉！", "project_id": project_id})
                append_event(thread_id, {"type": "assistant_chunk", "text": "ignored", "project_id": project_id})
                dialogue = load_recent_dialogue(project_id, thread_id)
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
                thread_id = create_thread_session(project_id)
                append_event(thread_id, {"type": "user", "text": "先幫我規劃", "project_id": project_id})
                append_event(
                    thread_id,
                    {
                        "type": "assistant",
                        "text": "好的，請問你想先做 UI 還是 API？",
                        "project_id": project_id,
                        "run_id": "run-123",
                    },
                )
                context = load_latest_run_context(project_id, thread_id)
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertEqual(context["run_id"], "run-123")
        self.assertEqual(context["last_assistant_text"], "好的，請問你想先做 UI 還是 API？")

    def test_rejects_invalid_thread_id_path_traversal(self) -> None:
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
                thread_id = create_thread_session(project_id)
                for idx in range(80):
                    append_event(thread_id, {"type": "user", "text": f"u{idx}", "project_id": project_id})
                    append_event(thread_id, {"type": "assistant", "text": f"a{idx}", "project_id": project_id})
                dialogue = load_recent_dialogue(project_id, thread_id, limit=4)
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

    def test_rollup_updates_after_user_and_assistant_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-rollup-001"
                thread_id = create_thread_session(project_id)
                append_event(thread_id, {"type": "user", "text": "先做後端", "project_id": project_id})
                append_event(
                    thread_id,
                    {
                        "type": "assistant",
                        "text": "好的，先建立 API。",
                        "project_id": project_id,
                        "run_id": "run-rollup-1",
                    },
                )
            finally:
                os.environ.pop("AMON_HOME", None)

            rollup_path = Path(temp_dir) / "projects" / project_id / ".amon" / "threads" / thread_id / "rollup.json"
            rollup = json.loads(rollup_path.read_text(encoding="utf-8"))
            self.assertEqual(rollup["thread_id"], thread_id)
            self.assertEqual(rollup["message_count"], 2)
            self.assertEqual(rollup["latest_run_id"], "run-rollup-1")
            self.assertEqual(rollup["run_count"], 1)
            self.assertEqual(rollup["last_user_text"], "先做後端")
            self.assertEqual(rollup["last_assistant_text"], "好的，先建立 API。")
            self.assertTrue(str(rollup.get("updated_at") or "").strip())

    def test_migration_moves_legacy_sessions_into_thread_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-migrate-001"
                legacy_dir = Path(temp_dir) / "projects" / project_id / "sessions" / "chat"
                legacy_dir.mkdir(parents=True, exist_ok=True)
                older = legacy_dir / "legacy-old.jsonl"
                newer = legacy_dir / "legacy-new.jsonl"
                older.write_text(json.dumps({"type": "user", "text": "舊訊息", "project_id": project_id}, ensure_ascii=False) + "\n", encoding="utf-8")
                newer.write_text(
                    "\n".join(
                        [
                            json.dumps({"type": "user", "text": "新任務", "project_id": project_id}, ensure_ascii=False),
                            json.dumps({"type": "assistant", "text": "新回覆", "project_id": project_id, "run_id": "run-new"}, ensure_ascii=False),
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                os.utime(older, (1000, 1000))
                os.utime(newer, (2000, 2000))

                ensured_thread_id, ensured_source = ensure_thread_session(project_id)
                context = load_latest_run_context(project_id, "legacy-new")
                dialogue = load_recent_dialogue(project_id, "legacy-new")
            finally:
                os.environ.pop("AMON_HOME", None)

            self.assertEqual(ensured_source, "active")
            self.assertEqual(ensured_thread_id, "legacy-new")
            self.assertEqual(context["run_id"], "run-new")
            self.assertEqual(dialogue[-1]["content"], "新回覆")

            project_state_path = Path(temp_dir) / "projects" / project_id / ".amon" / "project_state.json"
            state_payload = json.loads(project_state_path.read_text(encoding="utf-8"))
            self.assertEqual(state_payload.get("active_thread_id"), "legacy-new")

            migrated_events = Path(temp_dir) / "projects" / project_id / ".amon" / "threads" / "legacy-new" / "events.jsonl"
            self.assertTrue(migrated_events.exists())

    def test_active_thread_invariant_does_not_use_legacy_latest_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-active-001"
                first_thread_id = create_thread_session(project_id)
                second_thread_id = create_thread_session(project_id)

                first_event_path = Path(temp_dir) / "projects" / project_id / ".amon" / "threads" / first_thread_id / "events.jsonl"
                second_event_path = Path(temp_dir) / "projects" / project_id / ".amon" / "threads" / second_thread_id / "events.jsonl"
                os.utime(first_event_path, (3000, 3000))
                os.utime(second_event_path, (1000, 1000))

                ensured_thread_id, ensured_source = ensure_thread_session(project_id)
            finally:
                os.environ.pop("AMON_HOME", None)

            self.assertEqual(ensured_source, "active")
            self.assertEqual(ensured_thread_id, second_thread_id)


if __name__ == "__main__":
    unittest.main()
