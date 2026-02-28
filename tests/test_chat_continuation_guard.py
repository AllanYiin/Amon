from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from amon.chat.continuation import assemble_chat_turn
from amon.chat.session_store import append_event, create_chat_session


class ChatContinuationGuardTests(unittest.TestCase):
    def test_assemble_turn_uses_latest_chat_and_marks_short_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                project_id = "proj-cont-guard"
                chat_id = create_chat_session(project_id)
                append_event(chat_id, {"type": "user", "text": "請幫我規劃上線流程", "project_id": project_id})
                append_event(
                    chat_id,
                    {
                        "type": "assistant",
                        "text": "我已規劃完成，請選擇先做前端或後端",
                        "project_id": project_id,
                        "run_id": "run-guard-001",
                    },
                )

                bundle = assemble_chat_turn(project_id=project_id, chat_id=None, message="後端")
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertEqual(bundle.chat_id, chat_id)
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
                latest_chat_id = create_chat_session(project_id)
                append_event(latest_chat_id, {"type": "user", "text": "第一輪", "project_id": project_id})
                append_event(latest_chat_id, {"type": "assistant", "text": "第一輪回覆", "project_id": project_id})

                with patch("amon.chat.continuation.log_event") as mock_log_event:
                    bundle = assemble_chat_turn(project_id=project_id, chat_id="missing-chat-id", message="第二輪")
            finally:
                os.environ.pop("AMON_HOME", None)

        self.assertEqual(bundle.chat_id, latest_chat_id)
        self.assertEqual(bundle.chat_id_source, "latest")
        warning_events = [args[0] for args, _ in mock_log_event.call_args_list if args and isinstance(args[0], dict)]
        fallback_warning = [item for item in warning_events if item.get("event") == "chat_session_fallback"]
        self.assertTrue(fallback_warning)
        self.assertEqual(fallback_warning[0].get("incoming_chat_id"), "missing-chat-id")
        self.assertEqual(fallback_warning[0].get("fallback_chat_id"), latest_chat_id)


if __name__ == "__main__":
    unittest.main()
