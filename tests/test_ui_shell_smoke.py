from pathlib import Path
import unittest


class UIShellSmokeTests(unittest.TestCase):
    def test_index_contains_ui_shell_scaffold(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        for token in [
            "shell-sidebar",
            "toggle-context-panel",
            "toggle-sidebar",
            'data-i18n="nav.tools"',
            'data-shell-view="bill"',
            'id="bill-page"',
            'id="bill-breakdown-provider"',
            'id="shell-run-status"',
            'id="shell-daemon-status"',
            'id="shell-budget-status"',
            'id="inspector-execution"',
            'id="inspector-thinking"',
            'id="inspector-artifacts"',
            'id="artifacts-inline-preview"',
            'id="artifacts-inline-preview-frame"',
            'id="artifacts-list-details"',
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

    def test_graph_route_uses_dedicated_graph_page_and_supports_history_runs(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        shell_js = Path("src/amon/ui/static/js/views/shell.js").read_text(encoding="utf-8")
        graph_view_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")

        self.assertIn('id="graph-page"', html)
        self.assertIn('id="graph-run-select"', html)
        self.assertIn('id="graph-history-refresh"', html)
        self.assertIn('id="inspector-artifacts"', html)
        self.assertIn('graph: "graph"', shell_js)
        self.assertIn('ctx.services.graph.listRuns', graph_view_js)

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


    def test_artifact_panel_defaults_collapsed_and_expands_for_inline_named_blocks(self) -> None:
        inspector_js = Path("src/amon/ui/static/js/layout/inspector.js").read_text(encoding="utf-8")
        chat_js = Path("src/amon/ui/static/js/views/chat.js").read_text(encoding="utf-8")

        self.assertIn('const hasStoredCollapse = readStorage(storageKeys.contextCollapsed);', inspector_js)
        self.assertIn('const collapsed = hasStoredCollapse == null ? true : hasStoredCollapse === "1";', inspector_js)
        self.assertIn('activateArtifactsTab({ collapsed: true });', chat_js)
        self.assertIn('// 聊天頁預設維持右側收合，僅在偵測到具檔名 inline artifact 時展開', chat_js)
        self.assertIn('if (artifactEvent.type === "artifact_open") {', chat_js)
        self.assertIn('activateArtifactsTab({ collapsed: false });', chat_js)

    def test_styles_force_hidden_attribute_to_behave_like_tabs(self) -> None:
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        self.assertIn("[hidden]", css)
        self.assertIn("display: none !important", css)

    def test_artifact_preview_modal_body_is_scrollable(self) -> None:
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        self.assertIn(".artifact-preview-modal__panel", css)
        self.assertIn("grid-template-rows: auto auto minmax(0, 1fr);", css)
        self.assertIn("overflow: hidden;", css)
        self.assertIn(".artifact-preview-modal__body", css)
        self.assertIn("overflow: auto;", css)

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
            'id="context-waffle-grid"',
        ]:
            self.assertIn(token, html)

        for token in [
            'clearContextDraft("project")',
            'confirmModal.open({',
            'function getContextDraftStorageKey(projectIdOverride = undefined)',
            'return `${STORAGE_KEYS.contextDraftPrefix}project:${normalizedProjectId}`;',
        ]:
            self.assertIn(token, bootstrap_js)


    def test_context_view_uses_backend_stats_instead_of_local_estimate(self) -> None:
        context_js = Path("src/amon/ui/static/js/views/context.js").read_text(encoding="utf-8")

        self.assertIn("async function refreshContextStats", context_js)
        self.assertIn("ctx.services.context.getContextStats(projectId)", context_js)
        self.assertNotIn("estimateByContextText", context_js)
        self.assertNotIn("由草稿推估", context_js)

    def test_status_semantics_and_run_copy_controls_exist(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        self.assertIn('id="copy-run-id"', html)
        self.assertIn('mapDaemonStatusLevel', bootstrap_js)
        self.assertIn('createHeaderLayout', bootstrap_js)
        self.assertIn('daemonPill: { text: "Daemon：尚未連線"', bootstrap_js)
        self.assertIn('.context-resizer', css)
        self.assertIn('.context-waffle', css)

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

    def test_ui_server_exposes_graph_history_and_billing_series_endpoints(self) -> None:
        server_py = Path("src/amon/ui_server.py").read_text(encoding="utf-8")
        self.assertIn('if parsed.path == "/v1/billing/series"', server_py)
        self.assertIn('if parsed.path == "/v1/runs"', server_py)
        self.assertIn('if parsed.path.startswith("/v1/runs/") and parsed.path.endswith("/graph")', server_py)
        self.assertIn("def _list_runs_for_ui", server_py)
        self.assertIn("def _load_run_bundle", server_py)



if __name__ == "__main__":
    unittest.main()
