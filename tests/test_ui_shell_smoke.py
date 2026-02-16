from pathlib import Path
import unittest


class UIShellSmokeTests(unittest.TestCase):
    def test_index_contains_ui_shell_scaffold(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        for token in [
            "shell-sidebar",
            "toggle-context-panel",
            "toggle-sidebar",
            "Memory Used",
            'data-i18n="nav.tools"',
            'data-shell-view="bill"',
            'id="bill-page"',
            'id="bill-breakdown-provider"',
            'id="shell-run-status"',
            'id="shell-daemon-status"',
            'id="shell-budget-status"',
            'id="card-run-progress"',
            'id="card-billing"',
            'id="card-pending-confirmations"',
            'script type="module" src="/static/js/app.js"',
        ]:
            self.assertIn(token, html)

    def test_shell_navigation_uses_hash_routes(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        for token in [
            'href="#/chat"',
            'href="#/context"',
            'href="#/graph"',
            'href="#/tools"',
            'href="#/config"',
            'href="#/logs"',
            'href="#/docs"',
            'href="#/billing"',
        ]:
            self.assertIn(token, html)

        for token in [
            'window.addEventListener("hashchange"',
            'function resolveRouteFromHash',
            'function navigateToRoute(routeKey)',
            'createHashRouter',
            'event.preventDefault();',
            'navigateToRoute(routeKey);',
            'function normalizeProjectRecord(project = {})',
        ]:
            self.assertIn(token, bootstrap_js)

    def test_project_and_single_pages_redirect_to_index_hash_routes(self) -> None:
        project_html = Path("src/amon/ui/project.html").read_text(encoding="utf-8")
        single_html = Path("src/amon/ui/single.html").read_text(encoding="utf-8")

        self.assertIn('url=./index.html#/context', project_html)
        self.assertIn('href="./index.html#/context"', project_html)
        self.assertIn('url=./index.html#/chat', single_html)
        self.assertIn('href="./index.html#/chat"', single_html)

    def test_chat_stream_uses_view_renderers_and_orchestrator(self) -> None:
        chat_js = Path("src/amon/ui/static/js/views/chat.js").read_text(encoding="utf-8")
        message_renderer_js = Path("src/amon/ui/static/js/views/chat/renderers/messageRenderer.js").read_text(encoding="utf-8")
        timeline_renderer_js = Path("src/amon/ui/static/js/views/chat/renderers/timelineRenderer.js").read_text(encoding="utf-8")
        input_bar_js = Path("src/amon/ui/static/js/views/chat/renderers/inputBar.js").read_text(encoding="utf-8")

        self.assertIn("createMessageRenderer", chat_js)
        self.assertIn("createTimelineRenderer", chat_js)
        self.assertIn("createInputBar", chat_js)
        self.assertIn("appState.streamClient.start({", chat_js)
        self.assertIn('messageRenderer.applyTokenChunk(data.text || "")', chat_js)
        self.assertIn("applySessionFromEvent(data)", chat_js)
        self.assertIn("dataset.buffer", message_renderer_js)
        self.assertIn("applyExecutionEvent", timeline_renderer_js)
        self.assertIn("renderAttachmentPreview", input_bar_js)

    def test_styles_force_hidden_attribute_to_behave_like_tabs(self) -> None:
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        self.assertIn("[hidden]", css)
        self.assertIn("display: none !important", css)

    def test_context_page_has_actionable_cta_and_safe_clear_controls(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        for token in [
            'id="context-draft-input"',
            'id="context-save-draft"',
            'id="context-import-file"',
            'id="context-extract-chat"',
            'id="context-clear-chat"',
            'id="context-clear-project"',
        ]:
            self.assertIn(token, html)

        for token in ['clearContextDraft("project")', 'confirmModal.open({']:
            self.assertIn(token, bootstrap_js)

    def test_status_semantics_and_run_copy_controls_exist(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        self.assertIn('id="copy-run-id"', html)
        self.assertIn('mapDaemonStatusLevel', bootstrap_js)
        self.assertIn('createHeaderLayout', bootstrap_js)
        self.assertIn('daemonPill: { text: "Daemon：尚未連線"', bootstrap_js)
        self.assertIn('.context-resizer', css)

    def test_app_entry_only_bootstraps_composition_root(self) -> None:
        app_js = Path("src/amon/ui/static/js/app.js").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        self.assertIn('import { bootstrapApp } from "./bootstrap.js";', app_js)
        self.assertIn("bootstrapApp();", app_js)

        # entry 檔不應含 view/render 細節
        self.assertNotIn("createHashRouter", app_js)
        self.assertNotIn("createHeaderLayout", app_js)

        for token in [
            'createInitialUiState',
            'collectElements',
            'createSidebarLayout',
            'createHeaderLayout',
            'createInspectorLayout',
            'routeToShellView',
            'SHELL_VIEW_HANDLERS',
            'registerGlobalErrorHandlers',
        ]:
            self.assertIn(token, bootstrap_js)

        for module_path in [
            "src/amon/ui/static/js/store/app_state.js",
            "src/amon/ui/static/js/store/elements.js",
            "src/amon/ui/static/js/domain/storage.js",
            "src/amon/ui/static/js/domain/status.js",
            "src/amon/ui/static/js/layout/sidebar.js",
            "src/amon/ui/static/js/layout/header.js",
            "src/amon/ui/static/js/layout/inspector.js",
            "src/amon/ui/static/js/layout/splitPane.js",
            "src/amon/ui/static/js/views/shell.js",
            "src/amon/ui/static/js/views/config.js",
            "src/amon/ui/static/js/views/tools.js",
        ]:
            self.assertTrue(Path(module_path).exists(), module_path)



if __name__ == "__main__":
    unittest.main()
