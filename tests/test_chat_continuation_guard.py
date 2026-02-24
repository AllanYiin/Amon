from __future__ import annotations

import os
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
