from __future__ import annotations

import unittest

from amon.core_tool_templates import (
    render_native_tool_readme,
    render_native_tool_template,
    render_native_tool_test,
    render_tool_readme,
    render_tool_template,
    render_tool_test,
)


class CoreToolTemplateTests(unittest.TestCase):
    def test_render_tool_template_uppercase_branch(self) -> None:
        content = render_tool_template("demo", "將文字轉大寫")
        self.assertIn('result = text.upper()', content)
        self.assertIn('"""Amon tool: demo."""', content)

    def test_render_tool_template_passthrough_branch(self) -> None:
        content = render_tool_template("demo", "保留原文")
        self.assertIn('result = text', content)
        self.assertNotIn('result = text.upper()', content)

    def test_render_docs_and_tests_include_tool_name(self) -> None:
        self.assertIn("# demo", render_tool_readme("demo", "規格"))
        self.assertIn('Tool test for demo.', render_tool_test("demo"))

    def test_render_native_templates_include_tool_name(self) -> None:
        self.assertIn('name="native:demo"', render_native_tool_template("demo"))
        self.assertIn('native:demo', render_native_tool_readme("demo"))
        self.assertIn('Toolforge native tool test for demo.', render_native_tool_test("demo"))


if __name__ == "__main__":
    unittest.main()
