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
            "Daemon：尚未連線",
        ]:
            self.assertIn(token, html)



    def test_shell_navigation_uses_hash_routes(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        for token in [
            'href="#/chat"',
            'href="#/context"',
            'href="#/graph"',
            'href="#/tools"',
            'href="#/config"',
            'href="#/logs"',
            'href="#/docs"',
            'href="#/billing"',
            'window.addEventListener("hashchange"',
            'function resolveRouteFromHash',
            'function navigateToRoute(routeKey)',
        ]:
            self.assertIn(token, html)

    def test_project_and_single_pages_redirect_to_index_hash_routes(self) -> None:
        project_html = Path("src/amon/ui/project.html").read_text(encoding="utf-8")
        single_html = Path("src/amon/ui/single.html").read_text(encoding="utf-8")

        self.assertIn('target.hash = "#/context"', project_html)
        self.assertIn('href="./index.html#/context"', project_html)
        self.assertIn('target.hash = "#/chat"', single_html)
        self.assertIn('href="./index.html#/chat"', single_html)

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

    def test_context_page_has_actionable_cta_and_safe_clear_controls(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        for token in [
            'id="context-draft-input"',
            'id="context-save-draft"',
            'id="context-import-file"',
            'id="context-extract-chat"',
            'id="context-clear-chat"',
            'id="context-clear-project"',
            'clearContextDraft("project")',
            'confirmModal.open({',
        ]:
            self.assertIn(token, html)

    def test_status_semantics_and_run_copy_controls_exist(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")

        self.assertIn('id="copy-run-id"', html)
        self.assertIn('mapDaemonStatusLevel', html)
        self.assertIn('setStatusText(elements.shellDaemonStatus, "Daemon：Unavailable"', html)
        self.assertIn('.context-resizer', css)


if __name__ == "__main__":
    unittest.main()
