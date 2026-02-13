from pathlib import Path
import unittest


class UIShellSmokeTests(unittest.TestCase):
    def test_index_contains_ui_shell_scaffold(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        for token in [
            "shell-sidebar",
            "toggle-context-panel",
            "Memory Used",
            "Tools &amp; Skills",
            "data-shell-view=\"bill\"",
            "id=\"bill-page\"",
            "id=\"bill-breakdown-provider\"",
            "id=\"shell-run-status\"",
            "id=\"shell-daemon-status\"",
            "id=\"shell-budget-status\"",
            "id=\"card-run-progress\"",
            "id=\"card-billing\"",
            "id=\"card-pending-confirmations\"",
            "Daemon：Healthy",
        ]:
            self.assertIn(token, html)


    def test_chat_stream_uses_defined_render_paths(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        self.assertIn("state.streamClient.start({", html)
        self.assertIn('applyTokenChunk(data.text || "")', html)
        self.assertIn("applySessionFromEvent(data);", html)
        self.assertNotIn("agentBubble.innerHTML", html)
        self.assertNotIn("buffer += data.text", html)

    def test_styles_force_hidden_attribute_to_behave_like_tabs(self) -> None:
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        self.assertIn("[hidden]", css)
        self.assertIn("display: none !important", css)


if __name__ == "__main__":
    unittest.main()
