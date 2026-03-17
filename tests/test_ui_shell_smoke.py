from pathlib import Path
import unittest


class UIShellSmokeTests(unittest.TestCase):
    def test_index_contains_ui_shell_scaffold(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        for token in [
            "shell-sidebar",
            'id="thread-tree"',
            'id="thread-list"',
            'id="create-thread-btn"',
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
        self.assertIn('const sortedNodes = [...viewModel.nodes].sort((left, right) => left.order - right.order);', graph_view_js)

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
        self.assertIn("maxReconnectAttempts: 3", chat_js)
        self.assertIn('messageRenderer.applyTokenChunk(data.text || "")', chat_js)
        self.assertIn("applySessionFromEvent(data)", chat_js)
        self.assertIn("dataset.buffer", message_renderer_js)
        self.assertIn('const timestampText = String(meta.timestampText || "").trim();', message_renderer_js)
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

    def test_ui_defaults_to_light_theme_and_medium_font_size(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        self.assertIn('<html lang="zh-Hant" data-theme="light" data-font-size="md">', html)
        self.assertIn('html[data-theme="dark"]', css)
        self.assertIn('html[data-theme="light"]', css)
        self.assertIn('html[data-font-size="sm"]', css)
        self.assertIn('html[data-font-size="md"]', css)
        self.assertIn('html[data-font-size="lg"]', css)
        self.assertIn('--chat-font-size: 13px;', css)
        self.assertIn('font-size: var(--chat-font-size);', css)
        self.assertIn('function applyUiPreferencesFromConfig(effectiveConfig = {})', bootstrap_js)
        self.assertIn('rootEl.dataset.fontSize = normalizeUiFontSize(uiConfig.font_size);', bootstrap_js)

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
            'id="context-trace-box"',
            'id="context-trace-list"',
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

        self.assertIn("async function fetchContextStats", context_js)
        self.assertIn("async function refreshContextStats", context_js)
        self.assertIn("function renderLlmRequests", context_js)
        self.assertIn("OpenAI-like Messages", context_js)
        self.assertIn("payload?.llm_requests || []", context_js)
        self.assertIn("ctx.services.context.getContextStats(projectId)", context_js)
        self.assertIn("ctx.services.context.getContextStats(projectId, normalizedChatId)", context_js)
        self.assertIn("if (!normalizedChatId)", context_js)
        self.assertNotIn("estimateByContextText", context_js)
        self.assertNotIn("由草稿推估", context_js)

    def test_bootstrap_recovers_from_missing_project_during_context_and_artifact_load(self) -> None:
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        self.assertIn("function isMissingProjectError(error)", bootstrap_js)
        self.assertIn("async function recoverFromMissingProject(error, options = {})", bootstrap_js)
        self.assertIn("const { source } = options;", bootstrap_js)
        self.assertIn('if (isMissingProjectError(error)) {', bootstrap_js)
        self.assertIn('await recoverFromMissingProject(error, { source: "load_context" });', bootstrap_js)
        self.assertIn('await recoverFromMissingProject(error, { source: "load_run_artifacts", run_id: state.graphRunId || null });', bootstrap_js)
        self.assertIn("目前專案", bootstrap_js)
        self.assertIn("已清除失效狀態", bootstrap_js)

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

    def test_sidebar_thread_tree_styles_and_rollup_preview_tokens_exist(self) -> None:
        css = Path("src/amon/ui/styles.css").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        self.assertIn(".thread-tree", css)
        self.assertIn(".thread-row", css)
        self.assertIn(".thread-row.is-active", css)
        self.assertIn("function renderRollupPreview()", bootstrap_js)
        self.assertIn("sortThreadsForDisplay", bootstrap_js)
        self.assertIn("formatThreadUpdatedAt", bootstrap_js)

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

    def test_plan_card_renderers_exist_for_tool_policy_confirmation(self) -> None:
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")

        self.assertIn("function formatPlanListItem(item)", bootstrap_js)
        self.assertIn("function renderPlanList(container, items = [])", bootstrap_js)
        self.assertIn('emptyItem.textContent = "無";', bootstrap_js)
        self.assertIn("function renderPlanRisk(plan = {})", bootstrap_js)
        self.assertIn('renderPlanList(elements.planCommands, plan.commands || []);', bootstrap_js)
        self.assertIn('renderPlanList(elements.planPatches, plan.graph_patches || []);', bootstrap_js)

    def test_project_switch_uses_server_active_thread_and_hydration_token_guard(self) -> None:
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")
        thread_service_js = Path("src/amon/ui/static/js/domain/threadService.js").read_text(encoding="utf-8")
        app_state_js = Path("src/amon/ui/static/js/store/app_state.js").read_text(encoding="utf-8")

        self.assertIn("activeThreadId: null", app_state_js)
        self.assertIn("activeThreadByProject: {}", app_state_js)
        self.assertIn("threadList: []", app_state_js)
        self.assertIn("threadsByProject: {}", app_state_js)
        self.assertIn("pendingProjectLoadToken: 0", app_state_js)
        self.assertNotIn("projectThreads", app_state_js)
        self.assertNotIn('amon.ui.projectThreads', bootstrap_js)

        self.assertIn("function beginProjectHydration()", bootstrap_js)
        self.assertIn("function isCurrentProjectHydrationToken(token)", bootstrap_js)
        self.assertIn("await loadThreadList(token);", bootstrap_js)
        self.assertIn("await loadProjectHistory(token);", bootstrap_js)
        self.assertIn("await ensureActiveThread(token);", bootstrap_js)
        self.assertIn("await loadContext(token);", bootstrap_js)
        self.assertIn("if (!isCurrentProjectHydrationToken(token)) return;", bootstrap_js)
        self.assertIn("state.activeThreadId = payload.thread_id || null;", bootstrap_js)
        self.assertIn("state.activeThreadId = payload.active_thread_id || payload.thread_id || null;", bootstrap_js)
        self.assertIn("state.activeThreadByProject[state.projectId] = state.activeThreadId;", bootstrap_js)
        self.assertIn("await services.threads.setActiveThread(state.projectId, normalizedThreadId);", bootstrap_js)
        self.assertIn("elements.createThreadBtn?.addEventListener", bootstrap_js)
        self.assertIn("renderThreadList();", bootstrap_js)

        self.assertIn("async listProjectThreads(projectId)", thread_service_js)
        self.assertIn("async setActiveThread(projectId, threadId)", thread_service_js)
        self.assertIn("/active-thread", thread_service_js)
        self.assertIn('async getProjectThreadHistory(projectId, threadId = "")', thread_service_js)
        self.assertIn("/threads/", thread_service_js)


    def test_chat_view_stream_paths_use_thread_endpoints(self) -> None:
        chat_view_js = Path("src/amon/ui/static/js/views/chat.js").read_text(encoding="utf-8")
        self.assertIn('"/v1/threads/stream/init"', chat_view_js)
        self.assertIn('return `/v1/threads/stream?${query.toString()}`;', chat_view_js)
        self.assertIn('query.set("thread_id", params.thread_id);', chat_view_js)
        self.assertIn('thread_id: appState.activeThreadId', chat_view_js)
        self.assertIn("persistWhileStreaming: true", chat_view_js)
        self.assertNotIn('/v1/chat/stream', chat_view_js)

    def test_bootstrap_keeps_chat_view_mounted_while_streaming(self) -> None:
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")
        self.assertIn("if (state.streaming && viewDef?.persistWhileStreaming)", bootstrap_js)

    def test_ui_server_exposes_graph_history_and_billing_series_endpoints(self) -> None:
        server_py = Path("src/amon/ui_server.py").read_text(encoding="utf-8")
        self.assertIn('if parsed.path == "/v1/billing/series"', server_py)
        self.assertIn('if parsed.path == "/v1/runs"', server_py)
        self.assertIn('if parsed.path.startswith("/v1/runs/") and parsed.path.endswith("/graph")', server_py)
        self.assertIn("def _list_runs_for_ui", server_py)
        self.assertIn("def _load_run_bundle", server_py)



if __name__ == "__main__":
    unittest.main()
