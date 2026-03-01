import subprocess
import textwrap
import unittest
from pathlib import Path


class UIInlineArtifactParserTests(unittest.TestCase):
    def _run_node(self, script: str) -> None:
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            self.fail(
                "Node script failed\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

    def test_artifact_completes_on_fence_close(self) -> None:
        script = textwrap.dedent(
            """
            (async () => {
              const path = require('node:path');
              const { pathToFileURL } = require('node:url');
              const fileUrl = pathToFileURL(path.resolve('src/amon/ui/static/js/views/chat/renderers/streamingArtifactParser.js')).href;
              const { createStreamingArtifactParser } = await import(fileUrl);

              const parser = createStreamingArtifactParser();
              parser.feed('```html:index.html\\n');
              parser.feed('<h1>Hello</h1>\\n');
              const events = parser.feed('```\\n');
              const complete = events.find((item) => item.type === 'artifact_complete');
              if (!complete) {
                throw new Error('artifact_complete event missing after fence close');
              }
              if (complete.filename !== 'index.html') {
                throw new Error(`unexpected filename ${complete.filename}`);
              }
              if (!complete.content.includes('<h1>Hello</h1>')) {
                throw new Error(`unexpected content: ${complete.content}`);
              }
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )
        self._run_node(script)

    def test_unclosed_artifact_does_not_complete_on_finalize(self) -> None:
        script = textwrap.dedent(
            """
            (async () => {
              const path = require('node:path');
              const { pathToFileURL } = require('node:url');
              const fileUrl = pathToFileURL(path.resolve('src/amon/ui/static/js/views/chat/renderers/streamingArtifactParser.js')).href;
              const { createStreamingArtifactParser } = await import(fileUrl);

              const parser = createStreamingArtifactParser();
              parser.feed('```tsx filename=App.tsx\\n');
              parser.feed('export default function App(){\\n');
              parser.feed('  return <main>Hi</main>;\\n');
              parser.feed('}');

              const events = parser.finalizeClosedArtifacts();
              const complete = events.find((item) => item.type === 'artifact_complete');
              if (complete) {
                throw new Error('artifact_complete should not be emitted without closing fence');
              }
            })().catch((error) => {
              console.error(error);
              process.exit(1);
            });
            """
        )
        self._run_node(script)
