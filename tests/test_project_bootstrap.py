import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.chat.project_bootstrap import (
    build_project_name,
    choose_execution_mode,
    is_task_intent_message,
    resolve_project_id_from_message,
    should_bootstrap_project,
)


class ProjectBootstrapTests(unittest.TestCase):
    class _MockLLM:
        def __init__(self, payload: str):
            self.payload = payload

        def generate_stream(self, messages: list[dict[str, str]], model: str | None = None):
            _ = (messages, model)
            yield self.payload

    def test_should_bootstrap_when_task_intent_without_project(self) -> None:
        should_bootstrap = should_bootstrap_project(
            None,
            "chat_response",
            "請幫我整理這份影片企劃並輸出重點",
            llm_client=self._MockLLM('{"is_task_intent":true}'),
        )
        self.assertTrue(should_bootstrap)

    def test_should_not_bootstrap_for_greeting(self) -> None:
        self.assertFalse(is_task_intent_message("你好", llm_client=self._MockLLM('{"is_task_intent":false}')))

    def test_build_project_name_falls_back_to_message_snippet_when_parse_failed(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name("請幫我整理出 20 頁以上的投影片", "command_plan", _raise)

        self.assertEqual(name, "請幫我整理出 20 頁以上的投影片")

    def test_build_project_name_prefers_llm_summary_for_comparison_article_prompt(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name(
            "協助撰寫比較OpenClaw與Manus在記憶機制以及多agent任務同步機制比較的技術文章",
            "command_plan",
            _raise,
            llm_client=self._MockLLM('{"name":"撰寫OpenClaw與Manus技術文章"}'),
        )

        self.assertEqual(name, "撰寫OpenClaw與Manus技術文章")


    def test_build_project_name_falls_back_to_original_english_without_llm(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name(
            "Please create a concise execution plan for the marketing launch",
            "command_plan",
            _raise,
        )

        self.assertEqual(name, "Please create a concise execution plan for the marketing launch")


    def test_build_project_name_falls_back_to_original_cjk_without_llm(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name(
            "請幫我開發一個俄羅斯方塊遊戲並且提供分數排行榜與音效",
            "command_plan",
            _raise,
        )

        self.assertEqual(name, "請幫我開發一個俄羅斯方塊遊戲並且提供分數排行榜與音效")

    def test_build_project_name_prefers_llm_summary_for_cjk(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name(
            "請幫我開發一個俄羅斯方塊遊戲並且提供分數排行榜與音效",
            "command_plan",
            _raise,
            llm_client=self._MockLLM('{"name":"開發俄羅斯方塊"}'),
        )

        self.assertEqual(name, "開發俄羅斯方塊")

    def test_build_project_name_prefers_llm_summary_for_english(self) -> None:
        def _raise(_: str, __: str) -> tuple[str, dict]:
            raise ValueError("無法解析")

        name = build_project_name(
            "Please create a concise execution plan for the marketing launch",
            "command_plan",
            _raise,
            llm_client=self._MockLLM('{"name":"Marketing launch execution plan"}'),
        )

        self.assertEqual(name, "Marketing launch execution plan")

    def test_choose_execution_mode_prefers_self_critique_for_professional_writing(self) -> None:
        mode = choose_execution_mode(
            "協助撰寫比較OpenClaw與Manus在記憶機制以及多agent任務同步機制比較的技術文章",
            llm_client=self._MockLLM('{"mode":"self_critique","confidence":0.88,"rationale":["正式寫作"],"requires_planning":false}'),
        )
        self.assertEqual(mode, "self_critique")

    def test_choose_execution_mode_prefers_team_for_research_report(self) -> None:
        mode = choose_execution_mode(
            "請撰寫多agent協作架構的研究報告，需含方法論與驗證計畫",
            llm_client=self._MockLLM('{"mode":"team","confidence":0.92,"rationale":["跨領域分工"],"requires_planning":true}'),
        )
        self.assertEqual(mode, "team")

    def test_created_project_id_uses_neutral_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("開發一個俄羅斯方塊")

                self.assertRegex(project.project_id, r"^project-[0-9a-f]{6}$")
                self.assertNotEqual(Path(project.path).name, project.project_id)
            finally:
                os.environ.pop("AMON_HOME", None)

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
