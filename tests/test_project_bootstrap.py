import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.chat.project_bootstrap import build_project_name, is_task_intent_message, resolve_project_id_from_message, should_bootstrap_project


class ProjectBootstrapTests(unittest.TestCase):
    def test_should_bootstrap_when_task_intent_without_project(self) -> None:
        should_bootstrap = should_bootstrap_project(
            None,
            "chat_response",
            "請幫我整理這份影片企劃並輸出重點",
        )
        self.assertTrue(should_bootstrap)

    def test_should_not_bootstrap_for_greeting(self) -> None:
        self.assertFalse(is_task_intent_message("你好"))

    def test_build_project_name_falls_back_to_message_snippet_when_parse_failed(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name("請幫我整理出 20 頁以上的投影片", "command_plan", _raise)

        self.assertEqual(name, "整理出20頁以上的投影片")

    def test_build_project_name_summarizes_comparison_article_prompt(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name(
            "協助撰寫比較OpenClaw與Manus在記憶機制以及多agent任務同步機制比較的技術文章",
            "command_plan",
            _raise,
        )

        self.assertEqual(name, "撰寫OpenClaw與Manus技術文章")


    def test_build_project_name_limits_english_to_five_words(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name(
            "Please create a concise execution plan for the marketing launch",
            "command_plan",
            _raise,
        )

        self.assertEqual(name, "Please create a concise execution")

    def test_resolve_project_id_from_message_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("影片規格")

                matched = resolve_project_id_from_message(core, f"請套用專案 {project.project_id} 然後執行")

                self.assertEqual(matched, project.project_id)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_resolve_project_id_from_message_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("Anthropic Skills 規格")

                matched = resolve_project_id_from_message(core, "請延續 anthroPic skills 規格 的任務")

                self.assertEqual(matched, project.project_id)
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
