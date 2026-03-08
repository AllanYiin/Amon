from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from amon.chat.continuation import assemble_chat_turn
from amon.chat.thread_store import append_event, create_thread_session


class ChatContinuationGuardTests(unittest.TestCase):
    def test_assemble_turn_uses_active_chat_and_marks_short_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-cont-guard"
                thread_id = create_thread_session(project_id)
                append_event(thread_id, {"type": "user", "text": "請幫我規劃上線流程", "project_id": project_id})
                append_event(
                    thread_id,
                    {
                        "type": "assistant",
                        "text": "我已規劃完成，請選擇先做前端或後端",
                        "project_id": project_id,
                        "run_id": "run-guard-001",
                    },
                )

                bundle = assemble_chat_turn(project_id=project_id, thread_id=None, message="後端")
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertEqual(bundle.thread_id, thread_id)
        self.assertTrue(bundle.short_continuation)
        self.assertEqual(bundle.run_context.get("run_id"), "run-guard-001")
        self.assertEqual(
            bundle.history,
            [
                {"role": "user", "content": "請幫我規劃上線流程"},
                {"role": "assistant", "content": "我已規劃完成，請選擇先做前端或後端"},
            ],
        )
        self.assertIn("[歷史對話]", bundle.prompt_with_history)
        self.assertIn("使用者: 後端", bundle.prompt_with_history)

    def test_assemble_turn_fallback_logs_warning_when_incoming_chat_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-cont-fallback"
                active_thread_id = create_thread_session(project_id)
                append_event(active_thread_id, {"type": "user", "text": "第一輪", "project_id": project_id})
                append_event(active_thread_id, {"type": "assistant", "text": "第一輪回覆", "project_id": project_id})

                with patch("amon.chat.continuation.log_event") as mock_log_event:
                    bundle = assemble_chat_turn(project_id=project_id, thread_id="missing-chat-id", message="第二輪")
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertEqual(bundle.thread_id, active_thread_id)
        self.assertEqual(bundle.thread_id_source, "active")
        warning_events = [args[0] for args, _ in mock_log_event.call_args_list if args and isinstance(args[0], dict)]
        fallback_warning = [item for item in warning_events if item.get("event") == "thread_session_fallback"]
        self.assertTrue(fallback_warning)
        self.assertEqual(fallback_warning[0].get("incoming_thread_id"), "missing-chat-id")
        self.assertEqual(fallback_warning[0].get("fallback_thread_id"), active_thread_id)


if __name__ == "__main__":
    unittest.main()
