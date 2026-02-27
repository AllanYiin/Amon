from __future__ import annotations

import unittest

from amon.artifacts.parser import parse_artifact_blocks


class ArtifactsParserTests(unittest.TestCase):
    def test_parse_multiple_fences(self) -> None:
        content = (
            "```python file=workspace/app.py\n"
            "print('ok')\n"
            "```\n"
            "text\n"
            "```ts file=workspace/ui.ts\n"
            "export const x = 1;\n"
            "```\n"
        )
        blocks = parse_artifact_blocks(content)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].lang, "python")
        self.assertEqual(blocks[0].file_path, "workspace/app.py")
        self.assertIn("print('ok')", blocks[0].content)
        self.assertEqual(blocks[1].lang, "ts")


    def test_supports_filename_in_info_string(self) -> None:
        content = """```html filename=index.html
<h1>ok</h1>
```
"""
        blocks = parse_artifact_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].file_path, "index.html")
        self.assertEqual(blocks[0].lang, "html")

    def test_supports_header_filename_comment_when_info_missing(self) -> None:
        content = """```html
<!-- filename: index.html -->
<h1>ok</h1>
```
"""
        blocks = parse_artifact_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].file_path, "index.html")

    def test_skip_when_missing_file_token(self) -> None:
        content = "```python\nprint('x')\n```\n"
        self.assertEqual(parse_artifact_blocks(content), [])

    def test_unclosed_fence_is_ignored(self) -> None:
        content = "```python file=workspace/a.py\nprint('x')\n"
        self.assertEqual(parse_artifact_blocks(content), [])

    def test_info_string_whitespace(self) -> None:
        content = "```   python    file=workspace/a.py   \nprint('x')\n```\n"
        blocks = parse_artifact_blocks(content)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].lang, "python")
        self.assertEqual(blocks[0].file_path, "workspace/a.py")


if __name__ == "__main__":
    unittest.main()
