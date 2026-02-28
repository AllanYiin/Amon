from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


@unittest.skipIf(shutil.which("node") is None, "node is required for streaming artifact parser tests")
class StreamingArtifactParserTests(unittest.TestCase):
    def _run_parser_script(self, script: str) -> dict:
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def test_parses_colon_format_with_split_opening_fence(self) -> None:
        module_uri = (
            Path("src/amon/ui/static/js/views/chat/renderers/streamingArtifactParser.js")
            .resolve()
            .as_uri()
        )
        script = textwrap.dedent(
            f"""
            import {{ createStreamingArtifactParser }} from "{module_uri}";
            const parser = createStreamingArtifactParser();
            const events = [
              ...parser.feed("```ht"),
              ...parser.feed("ml:index.html\\n<body>"),
              ...parser.feed("ok</body>\\n```\\n"),
            ];
            console.log(JSON.stringify({{ events }}));
            """
        )
        payload = self._run_parser_script(script)
        events = payload["events"]

        self.assertEqual(events[0]["type"], "artifact_open")
        self.assertEqual(events[0]["language"], "html")
        self.assertEqual(events[0]["filename"], "index.html")
        self.assertEqual(events[0]["rawFenceLine"], "```html:index.html")

        self.assertEqual(events[1], {"type": "artifact_chunk", "filename": "index.html", "appendedText": "<body>ok</body>\n"})
        self.assertEqual(events[2]["type"], "artifact_complete")
        self.assertEqual(events[2]["content"], "<body>ok</body>\n")

    def test_parses_filename_equals_format(self) -> None:
        module_uri = (
            Path("src/amon/ui/static/js/views/chat/renderers/streamingArtifactParser.js")
            .resolve()
            .as_uri()
        )
        script = textwrap.dedent(
            f"""
            import {{ createStreamingArtifactParser }} from "{module_uri}";
            const parser = createStreamingArtifactParser();
            const events = parser.feed("```ts filename=main.ts\\nconst a = 1;\\n```\\n");
            console.log(JSON.stringify({{ events }}));
            """
        )
        payload = self._run_parser_script(script)
        events = payload["events"]

        self.assertEqual(events[0]["type"], "artifact_open")
        self.assertEqual(events[0]["filename"], "main.ts")
        self.assertEqual(events[0]["language"], "ts")
        self.assertEqual(events[-1]["type"], "artifact_complete")
        self.assertEqual(events[-1]["content"], "const a = 1;\n")


if __name__ == "__main__":
    unittest.main()
