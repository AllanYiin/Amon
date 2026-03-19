import { requestJson } from "./api.js";
import { createHashRouter } from "./router.js";
import { createStore } from "./state.js";
import { applyI18n, t } from "./i18n.js";
import { createToastManager } from "./ui/toast.js";
import { createConfirmModal } from "./ui/modal.js";
import { runBootstrapInitialization } from "./core/bootstrapInit.js";
import { createInitialUiState } from "./store/app_state.js";
import { collectElements } from "./store/elements.js";
import { readStorage, writeStorage, removeStorage } from "./domain/storage.js";
import { formatUnknownValue, shortenId, mapRunStatusLevel, mapDaemonStatusLevel, statusToI18nKey } from "./domain/status.js";
import { normalizeProjectIdForUi } from "./domain/projectId.js";
import { createAdminService } from "./domain/adminService.js";
import { createServices } from "./domain/services.js";
import { registerGlobalErrorHandlers } from "./domain/error_boundary.js";
import { routeToShellView, switchShellView } from "./views/shell.js";
import { CHAT_VIEW } from "./views/chat.js";
import { CONTEXT_VIEW } from "./views/context.js";
import { GRAPH_VIEW } from "./views/graph.js";
import { DOCS_VIEW } from "./views/docs.js";
import { BILLING_VIEW } from "./views/billing.js";
import { LOGS_VIEW } from "./views/logs.js";
import { CONFIG_VIEW } from "./views/config.js";
import { TOOLS_VIEW } from "./views/tools.js";
import { createEventBus } from "./core/bus.js";
import { copyText } from "./utils/clipboard.js";
import { createSidebarLayout } from "./layout/sidebar.js";
import { createHeaderLayout } from "./layout/header.js";
import { createInspectorLayout } from "./layout/inspector.js";
import { buildGraphRuntimeViewModel } from "./domain/graphRuntimeAdapter.js";
import { logUiDebug } from "./utils/debug.js";


export function bootstrapApp() {
const { EventStreamClient, createUiEventStore } = window.AmonUIEventStream || {};
if (!EventStreamClient || !createUiEventStore) {
  throw new Error("AmonUIEventStream 尚未載入，請確認 /event_stream_client.js");
}
applyI18n(document);
const appStore = createStore({ locale: "zh-TW" });
appStore.patch({ bootstrappedAt: Date.now() });

      const state = createInitialUiState(createUiEventStore);

      const elements = collectElements(document);
      const toolsSkillsUi = {
        activeTab: "tools",
        search: "",
        toolsFilter: "all",
        skillsSource: "all",
        skillsView: "grid",
      };
      const projectTreeUi = {
        expandedProjectIds: new Set(),
      };
      const TOOL_TYPE_META = {
        mcp: { label: "MCP", icon: "lan", tone: "info" },
        "built-in": { label: "System", icon: "build_circle", tone: "neutral" },
        forged: { label: "Custom", icon: "extension", tone: "warn" },
        unknown: { label: "Unknown", icon: "help", tone: "neutral" },
      };
      const TAB_SEQUENCE = ["tools", "skills"];

      function normalizeToolType(type) {
        const normalized = String(type || "unknown").trim().toLowerCase();
        return TOOL_TYPE_META[normalized] ? normalized : "unknown";
      }

      function extractToolMethodName(toolName) {
        const rawName = String(toolName || "");
        if (!rawName) return "(unnamed)";
        const separator = rawName.includes(":") ? ":" : ".";
        const parts = rawName.split(separator);
        return parts[parts.length - 1] || rawName;
      }

      function extractToolGroupName(tool) {
        const rawName = String(tool?.name || "");
        if (!rawName) return "default";
        if (rawName.includes(":")) {
          return rawName.split(":")[0] || "default";
        }
        if (rawName.includes(".")) {
          return rawName.split(".")[0] || "default";
        }
        return "default";
      }

      function getToolSearchText(tool) {
        return [
          tool?.name,
          tool?.type,
          tool?.risk,
          tool?.policy_decision,
          tool?.policy_reason,
          (tool?.allowed_paths || []).join(" "),
          JSON.stringify(tool?.input_schema || {}),
          JSON.stringify(tool?.output_schema || {}),
        ]
          .join(" ")
          .toLowerCase();
      }

      function getSkillSearchText(skill) {
        const frontmatter = skill?.frontmatter || {};
        return [
          skill?.name,
          skill?.description,
          frontmatter?.description,
          skill?.source,
          skill?.path,
        ]
          .join(" ")
          .toLowerCase();
      }

      function formatCatalogTimestamp(rawValue) {
        if (!rawValue) return "尚未同步";
        const timestamp = typeof rawValue === "number" ? rawValue : Date.parse(String(rawValue));
        if (!Number.isFinite(timestamp)) {
          return `同步：${String(rawValue)}`;
        }
        return `同步：${new Date(timestamp).toLocaleString("zh-TW", { hour12: false })}`;
      }

      function getLatestCatalogTimestamp() {
        const values = [state.toolsCatalogUpdatedAt, state.skillsCatalogUpdatedAt]
          .map((value) => (typeof value === "number" ? value : Date.parse(String(value || ""))))
          .filter((value) => Number.isFinite(value));
        if (!values.length) return "";
        return Math.max(...values);
      }

      function rememberExpandedProject(projectId) {
        const normalized = String(projectId || "").trim();
        if (!normalized) return;
        projectTreeUi.expandedProjectIds.add(normalized);
      }

      function getKnownProjects() {
        const layoutProjects = appStore.getState().layout?.projects || [];
        const normalizedProjects = sortProjectsForDisplay(layoutProjects.map(normalizeProjectRecord).filter(Boolean));
        const activeProjectId = String(state.projectId || "").trim();
        if (activeProjectId && !normalizedProjects.some((project) => project.project_id === activeProjectId)) {
          normalizedProjects.unshift({
            project_id: activeProjectId,
            name: "新專案",
          });
        }
        return normalizedProjects;
      }

      function getProjectLabel(projectId = state.projectId) {
        const normalizedProjectId = String(projectId || "").trim();
        if (!normalizedProjectId) return "無專案";
        return getKnownProjects().find((project) => project.project_id === normalizedProjectId)?.name || normalizedProjectId;
      }

      function isMissingProjectError(error) {
        const message = String(error?.message || error || "").trim();
        if (!message) return false;
        return message.includes("找不到專案") || message.toLowerCase().includes("project not found");
      }

      function toProjectDomId(projectId = "") {
        return String(projectId || "")
          .trim()
          .replace(/[^A-Za-z0-9_-]+/g, "-") || "project";
      }

      async function activateProject(projectId) {
        CHAT_VIEW.__chatStopStream?.();
        setProjectState(projectId);
        await refreshUiPreferences(state.projectId);
        await hydrateSelectedProject();
        await loadShellViewDependencies(state.shellView);
      }

      function buildToolFilterOptions(tools = []) {
        const options = [{ key: "all", label: "All", count: tools.length }];
        Array.from(new Set((tools || []).map((tool) => normalizeToolType(tool.type))))
          .sort((a, b) => a.localeCompare(b))
          .forEach((type) => {
            const meta = TOOL_TYPE_META[type] || TOOL_TYPE_META.unknown;
            options.push({
              key: type,
              label: meta.label,
              count: tools.filter((tool) => normalizeToolType(tool.type) === type).length,
            });
          });
        return options;
      }

      function buildSkillsSourceOptions(skills = []) {
        const options = [{ key: "all", label: "All", count: skills.length }];
        Array.from(new Set((skills || []).map((skill) => String(skill.source || "unknown"))))
          .sort((a, b) => a.localeCompare(b))
          .forEach((source) => {
            options.push({
              key: source,
              label: source,
              count: skills.filter((skill) => String(skill.source || "unknown") === source).length,
            });
          });
        return options;
      }

      function renderFilterChip(button) {
        return `
          <button
            type="button"
            class="chip${button.active ? " is-active" : ""}"
            ${button.dataset}
          >${escapeHtml(button.label)}<span class="chip__count">${escapeHtml(String(button.count))}</span></button>
        `;
      }

      function ensureToolsSkillsSelection() {
        const toolFilters = buildToolFilterOptions(state.toolsCatalog || []);
        const skillFilters = buildSkillsSourceOptions(state.skillsCatalog || []);
        if (!toolFilters.some((item) => item.key === toolsSkillsUi.toolsFilter)) {
          toolsSkillsUi.toolsFilter = "all";
        }
        if (!skillFilters.some((item) => item.key === toolsSkillsUi.skillsSource)) {
          toolsSkillsUi.skillsSource = "all";
        }
      }

      function setToolsSkillsTab(nextTab, { focus = false } = {}) {
        toolsSkillsUi.activeTab = nextTab === "skills" ? "skills" : "tools";
        const isTools = toolsSkillsUi.activeTab === "tools";
        elements.toolsPanel.hidden = !isTools;
        elements.skillsPanel.hidden = isTools;
        elements.toolsPanel.classList.toggle("is-active", isTools);
        elements.skillsPanel.classList.toggle("is-active", !isTools);
        elements.toolsSkillsTabTools.classList.toggle("is-active", isTools);
        elements.toolsSkillsTabSkills.classList.toggle("is-active", !isTools);
        elements.toolsSkillsTabTools.setAttribute("aria-selected", String(isTools));
        elements.toolsSkillsTabSkills.setAttribute("aria-selected", String(!isTools));
        elements.toolsSkillsTabTools.tabIndex = isTools ? 0 : -1;
        elements.toolsSkillsTabSkills.tabIndex = isTools ? -1 : 0;
        if (focus) {
          (isTools ? elements.toolsSkillsTabTools : elements.toolsSkillsTabSkills)?.focus();
        }
      }

      function syncToolsSkillsSummary(skillsPayload = {}) {
        const tools = state.toolsCatalog || [];
        const skills = state.skillsCatalog || [];
        const collisions = skillsPayload.collisions || state.skillsCollisions || [];
        const guardedCount = tools.filter((tool) => ["ask", "deny"].includes(String(tool.policy_decision || ""))).length;
        const latestTimestamp = getLatestCatalogTimestamp();

        elements.toolsSkillsToolsCount.textContent = String(tools.length);
        elements.toolsSkillsSkillsCount.textContent = String(skills.length);
        elements.toolsSkillsSummaryTools.textContent = String(tools.length);
        elements.toolsSkillsSummaryGuarded.textContent = String(guardedCount);
        elements.toolsSkillsSummarySkills.textContent = String(skills.length);
        elements.toolsSkillsSummaryOverrides.textContent = String(collisions.length);
        elements.toolsSkillsLastSync.textContent = formatCatalogTimestamp(latestTimestamp);
      }

      async function logToastEvent(entry = {}) {
        const payload = {
          level: entry.type === "danger" ? "ERROR" : entry.type === "warning" ? "WARNING" : "INFO",
          type: entry.type || "info",
          message: String(entry.message || "").slice(0, 600),
          message_length: String(entry.message || "").length,
          duration_ms: Number(entry.duration) || 12000,
          source: entry.source || "ui",
          route: window.location.hash || "#/chat",
          project_id: String(state.projectId || "").trim() || null,
          thread_id: String(state.activeThreadId || "").trim() || null,
          metadata: entry.metadata || {},
        };
        try {
          await requestJson("/v1/ui/toasts", {
            method: "POST",
            body: JSON.stringify(payload),
            timeoutMs: 5000,
          });
        } catch (error) {
          console.warn("toast_log_failed", error);
        }
      }

      const toastManager = createToastManager(elements.toast, { onShow: logToastEvent });
      const confirmModal = createConfirmModal(elements.confirmModal);

      const STORAGE_KEYS = {
        contextCollapsed: "amon.ui.contextPanelCollapsed",
        contextWidth: "amon.ui.contextPanelWidth",
        contextDraftPrefix: "amon.ui.contextDraft:",
      };

      function getContextDraftStorageKey(projectIdOverride = undefined) {
        const resolvedProjectId = projectIdOverride === undefined ? state.projectId : projectIdOverride;
        const normalizedProjectId = String(resolvedProjectId || "").trim();
        if (normalizedProjectId) {
          return `${STORAGE_KEYS.contextDraftPrefix}project:${normalizedProjectId}`;
        }

        const normalizedThreadId = String(state.activeThreadId || "").trim();
        if (normalizedThreadId) {
          return `${STORAGE_KEYS.contextDraftPrefix}thread:${normalizedThreadId}`;
        }

        return `${STORAGE_KEYS.contextDraftPrefix}default`;
      }

      const isMobileViewport = window.innerWidth < 768;
      appStore.patch({
        layout: {
          activeRoute: "chat",
          sidebarCollapsed: isMobileViewport,
          projectId: state.projectId,
          projects: [],
          runPill: { text: t("status.run.idle"), level: "neutral", title: t("tooltip.runIdle") },
          daemonPill: { text: "Daemon：尚未連線", level: "neutral", title: t("tooltip.daemonIdle") },
          budgetPill: "Budget：NT$ 0.00 / NT$ 5,000",
          inspector: {
            collapsed: isMobileViewport,
            width: state.contextPanelWidth,
            activeTab: "thinking",
          },
        },
      });

      const sidebarLayout = createSidebarLayout({ elements, store: appStore });
      const headerLayout = createHeaderLayout({ elements, store: appStore });
      const inspectorLayout = createInspectorLayout({
        elements,
        store: appStore,
        storage: { readStorage, writeStorage },
        storageKeys: STORAGE_KEYS,
      });

      sidebarLayout.mount();
      headerLayout.mount();
      inspectorLayout.mount();

      const router = createHashRouter({
        routes: routeToShellView,
        defaultRoute: "chat",
        onRoute: async (routeKey) => {
          await applyRoute(routeKey);
        },
      });

      function resolveRouteFromHash(hashValue = window.location.hash) {
        return router.parse(hashValue);
      }

      const apiClient = {
        /** @param {string} path @param {RequestInit & {quiet?: boolean}} [options] */
        request(path, options = {}) {
          return requestJson(`/v1${path}`, options);
        },
      };
      const bus = createEventBus();
      const ui = { toast: toastManager, modal: confirmModal };
      const adminService = createAdminService({ api: apiClient });
      const domainServices = createServices({ api: apiClient });
      const services = {
        ...domainServices,
        admin: {
          ...adminService,
          loadDocsPage,
          loadBillPage,
          loadLogsEventsPage,
          loadConfigPage,
          loadToolsSkillsPage,
        },
      };

      const VIEW_ROOTS = {
        chat: elements.chatLayout,
        context: elements.contextPage,
        graph: elements.graphPage,
        "tools-skills": elements.toolsSkillsPage,
        bill: elements.billPage,
        config: elements.configPage,
        "logs-events": elements.logsEventsPage,
        docs: elements.docsPage,
      };

      const SHELL_VIEW_HANDLERS = [
        CHAT_VIEW,
        CONTEXT_VIEW,
        GRAPH_VIEW,
        DOCS_VIEW,
        BILLING_VIEW,
        LOGS_VIEW,
        CONFIG_VIEW,
        TOOLS_VIEW,
      ].reduce((acc, viewDef) => {
        acc[viewDef.id] = viewDef;
        return acc;
      }, {});

      const mountedViews = new Set();

      function buildViewContext(viewId) {
        return {
          rootEl: VIEW_ROOTS[viewId],
          store: appStore,
          services,
          ui,
          t,
          bus,
          appState: state,
          elements,
          chatDeps: {
            renderMarkdown,
            escapeHtml,
            shortenId,
            formatUnknownValue,
            mapDaemonStatusLevel,
            updateThinking,
            resetPlanCard,
            showPlanCard,
            applySessionFromEvent,
            loadProjects,
            loadContext,
            appendArtifactsHintToTimeline,
          },
        };
      }

      async function loadShellViewDependencies(view) {
        const viewDef = SHELL_VIEW_HANDLERS[view];
        if (!viewDef) return;
        if (!mountedViews.has(view) && typeof viewDef.mount === "function") {
          viewDef.mount(buildViewContext(view));
          mountedViews.add(view);
          bus.emit("view:mounted", { view });
        }
        if (typeof viewDef.onRoute === "function") {
          await viewDef.onRoute({}, buildViewContext(view));
        }
      }

      function unmountInactiveViews(activeView) {
        mountedViews.forEach((viewId) => {
          if (viewId === activeView) return;
          const viewDef = SHELL_VIEW_HANDLERS[viewId];
          if (state.streaming && viewDef?.persistWhileStreaming) {
            return;
          }
          if (viewDef && typeof viewDef.unmount === "function") {
            viewDef.unmount();
          }
          mountedViews.delete(viewId);
        });
      }

      async function applyRoute(routeKey) {
        const view = routeToShellView[routeKey] || "chat";
        switchShellView({ view, state, elements, closeBillingStream });
        bus.emit("run:changed", { view });
        appStore.patch({
          layout: {
            ...(appStore.getState().layout || {}),
            activeRoute: routeKey,
          },
        });
        await loadShellViewDependencies(view);
        unmountInactiveViews(view);
      }

      function navigateToRoute(routeKey) {
        const normalized = routeToShellView[routeKey] ? routeKey : "chat";
        const targetHash = `#/${normalized}`;
        if (window.location.hash === targetHash) {
          void applyRoute(normalized);
          return;
        }
        router.navigate(normalized);
      }

      function formatConfigCell(value) {
        if (value === undefined) return "-";
        if (value === null) return "null";
        if (typeof value === "string") return value;
        return JSON.stringify(value);
      }

      function formatConfigEditorValue(value) {
        return JSON.stringify(value);
      }

      function populateConfigEditor(keyPath, value, source = "project") {
        if (!elements.configEditKey || !elements.configEditValue || !elements.configEditScope) return;
        elements.configEditKey.value = keyPath || "";
        elements.configEditValue.value = formatConfigEditorValue(value);
        elements.configEditScope.value = source === "global" ? "global" : "project";
      }

      function parseConfigEditorValue(rawValue) {
        const text = String(rawValue || "").trim();
        if (!text) {
          throw new Error("請輸入 Value（JSON 格式）。");
        }
        try {
          return JSON.parse(text);
        } catch (_error) {
          throw new Error("Value 必須是合法 JSON，例如 \"light\"、true、123、null。");
        }
      }

      function normalizeUiTheme(rawTheme) {
        return String(rawTheme || "").toLowerCase() === "dark" ? "dark" : "light";
      }

      function normalizeUiFontSize(rawFontSize) {
        const normalized = String(rawFontSize || "").toLowerCase();
        return ["sm", "md", "lg"].includes(normalized) ? normalized : "md";
      }

      function applyUiPreferencesFromConfig(effectiveConfig = {}) {
        const uiConfig = effectiveConfig && typeof effectiveConfig === "object" ? effectiveConfig.ui || {} : {};
        const rootEl = document.documentElement;
        rootEl.dataset.theme = normalizeUiTheme(uiConfig.theme);
        rootEl.dataset.fontSize = normalizeUiFontSize(uiConfig.font_size);
      }

      async function refreshUiPreferences(projectId = state.projectId) {
        const payload = await services.admin.getConfigView(projectId || "");
        state.configView = payload;
        applyUiPreferencesFromConfig(payload?.effective_config || {});
      }

      function flattenConfigRows(effective, sources, prefix = "") {
        if (!effective || typeof effective !== "object" || Array.isArray(effective)) {
          return [{ keyPath: prefix || "(root)", effective, source: sources || "default" }];
        }
        const rows = [];
        Object.entries(effective).forEach(([key, value]) => {
          const keyPath = prefix ? `${prefix}.${key}` : key;
          const sourceValue = sources && typeof sources === "object" ? sources[key] : undefined;
          if (value && typeof value === "object" && !Array.isArray(value)) {
            rows.push(...flattenConfigRows(value, sourceValue, keyPath));
            return;
          }
          rows.push({ keyPath, effective: value, source: sourceValue || "default" });
        });
        return rows;
      }

      function renderConfigTable() {
        const payload = state.configView;
        if (!payload) {
          elements.configGlobal.textContent = "尚未載入。";
          elements.configProject.textContent = "尚未載入。";
          elements.configEffectiveSummary.textContent = "尚未載入。";
          elements.configTableBody.innerHTML = "";
          if (elements.plannerEnabledStatus) elements.plannerEnabledStatus.textContent = "尚未載入。";
          if (elements.plannerEnabledSource) elements.plannerEnabledSource.textContent = "來源：--";
          if (elements.plannerToggleBtn) elements.plannerToggleBtn.disabled = true;
          return;
        }
        elements.configGlobal.textContent = JSON.stringify(payload.global_config || {}, null, 2);
        elements.configProject.textContent = JSON.stringify(payload.project_config || {}, null, 2);
        const planner = payload.planner || {};
        if (elements.plannerEnabledStatus) {
          const plannerEnabled = Boolean(planner.enabled);
          elements.plannerEnabledStatus.textContent = plannerEnabled ? "目前為啟用（graph 預設走 planner）" : "目前為停用（graph 會 fallback 到 single）";
        }
        if (elements.plannerEnabledSource) {
          elements.plannerEnabledSource.textContent = `來源：${planner.source || "default"}`;
        }
        if (elements.plannerToggleBtn) {
          const plannerEnabled = Boolean(planner.enabled);
          elements.plannerToggleBtn.disabled = planner.toggle_allowed === false;
          elements.plannerToggleBtn.textContent = plannerEnabled ? "停用 Planner" : "啟用 Planner";
        }
        const webConfig = payload.effective_config?.web || {};
        if (elements.configSerpapiKeyEnv) {
          elements.configSerpapiKeyEnv.value = String(webConfig.serpapi_key_env || "SERPAPI_KEY");
        }
        if (elements.configSearchPriority) {
          const priority = Array.isArray(webConfig.search_provider_priority)
            ? webConfig.search_provider_priority
            : ["serpapi", "google", "bing"];
          elements.configSearchPriority.value = priority.join(",");
        }

        const keyword = (elements.configSearch.value || "").trim().toLowerCase();
        const rows = flattenConfigRows(payload.effective_config || {}, payload.sources || {});
        const filtered = keyword ? rows.filter((row) => row.keyPath.toLowerCase().includes(keyword)) : rows;
        elements.configEffectiveSummary.textContent = `共 ${rows.length} 筆 leaf 設定，篩選後 ${filtered.length} 筆。來源包含：default / global / project / cli / chat。`;
        elements.configTableBody.innerHTML = "";

        filtered.forEach((row) => {
          const tr = document.createElement("tr");
          const sourceLabel = ["default", "global", "project", "cli", "chat"].includes(row.source) ? row.source : "default";
          tr.innerHTML = `
            <td><code>${escapeHtml(row.keyPath)}</code></td>
            <td><code>${escapeHtml(formatConfigCell(row.effective))}</code></td>
            <td><span class="config-source config-source--${sourceLabel}">${sourceLabel}</span></td>
            <td><button type="button" class="btn btn--secondary secondary-btn" data-config-key="${escapeHtml(row.keyPath)}">編輯</button></td>
          `;
          const editButton = tr.querySelector("button[data-config-key]");
          if (editButton) {
            editButton.addEventListener("click", () => {
              populateConfigEditor(row.keyPath, row.effective, sourceLabel);
            });
          }
          elements.configTableBody.appendChild(tr);
        });
      }

      async function loadConfigPage() {
        const payload = await services.admin.getConfigView(state.projectId);
        state.configView = payload;
        applyUiPreferencesFromConfig(payload?.effective_config || {});
        renderConfigTable();
      }

      async function applyConfigUpdate() {
        const keyPath = String(elements.configEditKey?.value || "").trim();
        if (!keyPath) {
          showToast("請填寫 key path。", 8000, "warning");
          return;
        }
        const scope = elements.configEditScope?.value === "global" ? "global" : "project";
        if (scope === "project" && !state.projectId) {
          showToast("目前尚未選擇專案，無法寫入 project scope。", 8000, "warning");
          return;
        }
        let parsedValue;
        try {
          parsedValue = parseConfigEditorValue(elements.configEditValue?.value || "");
        } catch (error) {
          showToast(error.message || "Value 格式錯誤。", 10000, "warning");
          return;
        }
        const response = await services.admin.setConfigValue({
          projectId: scope === "project" ? (state.projectId || "") : "",
          keyPath,
          value: parsedValue,
          scope,
        });
        state.configView = response.config || state.configView;
        applyUiPreferencesFromConfig(state.configView?.effective_config || {});
        renderConfigTable();
        showToast(`已更新 ${keyPath}（${scope}）。`, 8000, "info");
      }

      async function applyWebSearchConfig() {
        const serpapiEnv = String(elements.configSerpapiKeyEnv?.value || "").trim() || "SERPAPI_KEY";
        const priorityRaw = String(elements.configSearchPriority?.value || "").trim();
        const providerPriority = (priorityRaw || "serpapi,google,bing")
          .split(",")
          .map((item) => item.trim().toLowerCase())
          .filter((item, idx, arr) => item && ["serpapi", "google", "bing"].includes(item) && arr.indexOf(item) === idx);
        if (!providerPriority.length) {
          showToast("搜尋提供者優先序至少要包含 serpapi/google/bing 其中之一。", 10000, "warning");
          return;
        }
        if (!state.projectId) {
          showToast("目前尚未選擇專案，無法寫入 project scope。", 8000, "warning");
          return;
        }
        const updates = [
          { keyPath: "web.serpapi_key_env", value: serpapiEnv },
          { keyPath: "web.search_provider_priority", value: providerPriority },
        ];
        let latestConfig = state.configView;
        for (const update of updates) {
          const response = await services.admin.setConfigValue({
            projectId: state.projectId,
            keyPath: update.keyPath,
            value: update.value,
            scope: "project",
          });
          latestConfig = response.config || latestConfig;
        }
        state.configView = latestConfig;
        applyUiPreferencesFromConfig(state.configView?.effective_config || {});
        renderConfigTable();
        showToast("已更新 Web Search 偏好設定。", 8000, "info");
      }

      async function togglePlannerEnabled() {
        const planner = state.configView?.planner || {};
        const nextEnabled = !Boolean(planner.enabled);
        const response = await services.admin.setPlannerEnabled({ projectId: state.projectId || "", enabled: nextEnabled });
        state.configView = response.config || state.configView;
        applyUiPreferencesFromConfig(state.configView?.effective_config || {});
        renderConfigTable();
        showToast(nextEnabled ? "Planner 已啟用。" : "Planner 已停用，graph 會 fallback。", 8000, "info");
      }

      function formatBillMetric(cost, usage, currency) {
        return `${currency} ${Number(cost || 0).toFixed(2)} / ${Number(usage || 0).toFixed(2)}`;
      }

      function formatBreakdown(payload = {}) {
        const entries = Object.entries(payload || {});
        if (!entries.length) return "尚無資料";
        return entries
          .sort((a, b) => Number(b[1]?.cost || 0) - Number(a[1]?.cost || 0))
          .map(
            ([key, value]) =>
              `${key}\n  cost: ${Number(value?.cost || 0).toFixed(4)}\n  usage: ${Number(value?.usage || 0).toFixed(4)}\n  records: ${Number(value?.records || 0)}`
          )
          .join("\n\n");
      }

      function renderBillPage() {
        const payload = state.billingSummary;
        if (!payload) {
          elements.billToday.textContent = "--";
          elements.billProjectTotal.textContent = "--";
          elements.billModeSummary.textContent = "--";
          elements.billCurrentRun.textContent = "--";
          elements.billBudgets.textContent = "尚未載入。";
          elements.billExceeded.innerHTML = "";
          elements.billBreakdownProvider.textContent = "尚未載入。";
          elements.billBreakdownModel.textContent = "尚未載入。";
          elements.billBreakdownAgent.textContent = "尚未載入。";
          elements.billBreakdownNode.textContent = "尚未載入。";
          renderBillRunChart([]);
          return;
        }
        const currency = payload.currency || "USD";
        elements.billToday.textContent = formatBillMetric(payload.today?.cost, payload.today?.usage, currency);
        elements.billProjectTotal.textContent = formatBillMetric(payload.project_total?.cost, payload.project_total?.usage, currency);
        elements.billModeSummary.textContent = `automation ${formatBillMetric(payload.mode_breakdown?.automation?.cost, payload.mode_breakdown?.automation?.usage, currency)}｜interactive ${formatBillMetric(payload.mode_breakdown?.interactive?.cost, payload.mode_breakdown?.interactive?.usage, currency)}`;
        elements.billCurrentRun.textContent = formatBillMetric(payload.current_run?.cost, payload.current_run?.usage, currency);
        elements.billBudgets.textContent = JSON.stringify(payload.budgets || {}, null, 2);
        elements.billBreakdownProvider.textContent = formatBreakdown(payload.breakdown?.provider);
        elements.billBreakdownModel.textContent = formatBreakdown(payload.breakdown?.model);
        elements.billBreakdownAgent.textContent = formatBreakdown(payload.breakdown?.agent);
        elements.billBreakdownNode.textContent = formatBreakdown(payload.breakdown?.node);
        renderBillRunChart(payload.run_trend || [], currency);

        elements.billExceeded.innerHTML = "";
        (payload.exceeded_events || []).forEach((event) => {
          const card = document.createElement("article");
          card.className = "log-item";
          card.innerHTML = `<header><strong>budget_exceeded</strong> · <code>${escapeHtml(event.ts || "-")}</code></header><pre>${escapeHtml(JSON.stringify(event, null, 2))}</pre>`;
          elements.billExceeded.appendChild(card);
        });
        if (!payload.exceeded_events || !payload.exceeded_events.length) {
          elements.billExceeded.textContent = "目前沒有超限事件。";
        }
      }

      function renderBillRunChart(series = [], currency = "USD") {
        if (!elements.billRunChart || !window.Chart) return;
        const labels = series.map((item) => item.run_id || "(unknown)");
        const values = series.map((item) => Number(item.cost || 0));
        if (state.billRunChart) {
          state.billRunChart.destroy();
          state.billRunChart = null;
        }
        state.billRunChart = new Chart(elements.billRunChart, {
          type: "bar",
          data: {
            labels,
            datasets: [{
              label: `每 Run 花費（${currency}）`,
              data: values,
              backgroundColor: "rgba(37, 99, 235, 0.5)",
              borderColor: "rgba(37, 99, 235, 1)",
              borderWidth: 1,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } },
          },
        });
      }

      function closeBillingStream() {
        if (state.billingStreamSource) {
          state.billingStreamSource.close();
          state.billingStreamSource = null;
        }
      }

      function openBillingStream() {
        closeBillingStream();
        const params = new URLSearchParams();
        if (state.projectId) {
          params.set("project_id", state.projectId);
        }
        const source = new EventSource(`/v1/billing/stream?${params.toString()}`);
        source.addEventListener("usage_updated", (event) => {
          state.billingSummary = JSON.parse(event.data || "{}");
          renderBillPage();
        });
        source.addEventListener("budget_exceeded", () => {
          showToast("偵測到 budget_exceeded 事件，已同步 Bill。", 4500);
        });
        source.onerror = () => {
          closeBillingStream();
        };
        state.billingStreamSource = source;
      }

      async function loadBillPage() {
        const payload = await services.admin.getBillingSummary(state.projectId);
        state.billingSummary = payload;
        renderBillPage();
        openBillingStream();
      }

      function exportEffectiveConfig() {
        if (!state.configView) {
          showToast("請先載入 Config。");
          return;
        }
        const blob = new Blob([JSON.stringify(state.configView.effective_config || {}, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        const projectSuffix = state.projectId ? `-${state.projectId}` : "-global";
        link.href = url;
        link.download = `amon-effective-config${projectSuffix}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      }

      function fromDateInput(value) {
        if (!value) return "";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "";
        return date.toISOString();
      }

      function getLevelKey(value) {
        return String(value || "info").trim().toLowerCase();
      }

      function formatLogTime(value) {
        if (!value) return "-";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString("zh-TW", { hour12: false });
      }

      function getLogMessage(item = {}) {
        const candidates = [item.message, item.msg, item.summary, item.detail, item.event, item.type];
        const found = candidates.find((text) => String(text || "").trim());
        return found ? String(found) : "(無訊息內容)";
      }

      function formatMetaLine(item = {}) {
        const pairs = [
          ["project", item.project_id],
          ["run", item.run_id],
          ["node", item.node_id],
          ["component", item.component],
        ].filter(([, value]) => value);
        return pairs.map(([key, value]) => `${key}:${value}`).join(" · ") || "-";
      }

      function stringifyTimelineItem(item = {}, options = {}) {
        const { isEvent = false } = options;
        const levelRaw = isEvent ? "EVENT" : item.level || item.severity || "INFO";
        const title = String(isEvent ? item.event || item.type || "event" : levelRaw).toUpperCase();
        const rows = [
          `time: ${formatLogTime(item.ts || item.time || item.timestamp)}`,
          `title: ${title}`,
          `message: ${getLogMessage(item)}`,
          `meta: ${formatMetaLine(item)}`,
          `raw: ${JSON.stringify(item)}`,
        ];
        return rows.join("\n");
      }

      function getVisibleItemsText(payload = {}, options = {}) {
        const { isEvent = false, keyword = "" } = options;
        const items = (payload.items || []).filter((item) => matchesSearch(item, keyword));
        if (!items.length) {
          return "";
        }
        return items.map((item) => stringifyTimelineItem(item, { isEvent })).join("\n\n--------------------\n\n");
      }

      function matchesSearch(item = {}, keyword = "") {
        const normalized = String(keyword || "").trim().toLowerCase();
        if (!normalized) return true;
        return JSON.stringify(item).toLowerCase().includes(normalized);
      }

      function setLogsEventsPanel(panelName = "logs") {
        const showLogs = panelName !== "events";
        elements.logsPanel.hidden = !showLogs;
        elements.eventsPanel.hidden = showLogs;
        elements.logsTabLogs.classList.toggle("is-active", showLogs);
        elements.logsTabEvents.classList.toggle("is-active", !showLogs);
        elements.logsTabLogs.setAttribute("aria-pressed", showLogs ? "true" : "false");
        elements.logsTabEvents.setAttribute("aria-pressed", showLogs ? "false" : "true");
      }

      function setSeverityChipActive(severityValue = "") {
        const targetValue = String(severityValue || "").toUpperCase();
        elements.logsSeverityChips?.querySelectorAll(".chip[data-severity]").forEach((chip) => {
          const chipValue = String(chip.dataset.severity || "").toUpperCase();
          chip.classList.toggle("is-active", chipValue === targetValue || (!chipValue && !targetValue));
        });
      }

      function createTimelineItem(item = {}, options = {}) {
        const { isEvent = false } = options;
        const article = document.createElement("article");
        const levelRaw = isEvent ? "EVENT" : item.level || item.severity || "INFO";
        const levelKey = getLevelKey(levelRaw);
        article.className = "logs-timeline-item";
        article.dataset.level = levelKey;

        const eventType = item.event || item.type || "event";
        const title = isEvent ? eventType : levelRaw;
        const rawJsonPretty = JSON.stringify(item, null, 2);
        const itemText = stringifyTimelineItem(item, { isEvent });

        article.innerHTML = `
          <div class="logs-timeline-item__time">${escapeHtml(formatLogTime(item.ts || item.time || item.timestamp))}</div>
          <div class="logs-timeline-item__content">
            <span class="logs-timeline-item__dot" aria-hidden="true"></span>
            <div class="logs-timeline-item__head">
              <span class="pill ${isEvent ? "pill--info" : `pill--${levelKey === "warning" || levelKey === "warn" ? "warn" : levelKey === "error" || levelKey === "critical" || levelKey === "fatal" ? "error" : levelKey === "debug" ? "neutral" : "info"}`}">${escapeHtml(String(title).toUpperCase())}</span>
              ${isEvent ? "" : `<code>${escapeHtml(item.id || item.log_id || "")}</code>`}
            </div>
            <p class="logs-timeline-item__message">${escapeHtml(getLogMessage(item))}</p>
            <div class="logs-timeline-item__meta">${escapeHtml(formatMetaLine(item))}</div>
            <div class="logs-timeline-item__actions">
              <button type="button" class="btn btn--secondary secondary-btn small" data-copy-log-item="true">複製此筆</button>
            </div>
            <details>
              <summary>
                <span>Raw JSON</span>
                <button type="button" class="btn btn--secondary secondary-btn small" data-copy-raw-json="true">複製 Raw JSON</button>
              </summary>
              <pre class="logs-timeline-item__json">${escapeHtml(rawJsonPretty)}</pre>
            </details>
          </div>
        `;
        const copyItemBtn = article.querySelector('[data-copy-log-item="true"]');
        copyItemBtn?.addEventListener("click", async () => {
          await copyText(itemText, {
            toast: (message, options = {}) => showToast(message, options.duration || 7000, options.type || "success"),
            successMessage: "已複製此筆明細。",
            errorMessage: "複製失敗，請手動選取內容。",
          });
        });
        const copyRawBtn = article.querySelector('[data-copy-raw-json="true"]');
        copyRawBtn?.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          await copyText(rawJsonPretty, {
            toast: (message, options = {}) => showToast(message, options.duration || 7000, options.type || "success"),
            successMessage: "已複製 Raw JSON。",
            errorMessage: "複製失敗，請手動選取 Raw JSON。",
          });
        });
        return article;
      }

      function buildLogsQuery(page) {
        const params = new URLSearchParams({ source: elements.logsSource.value, page: String(page), page_size: "50" });
        [
          ["project_id", elements.logsFilterProject.value || state.projectId || ""],
          ["run_id", elements.logsFilterRun.value],
          ["node_id", elements.logsFilterNode.value],
          ["severity", elements.logsFilterSeverity.value],
          ["component", elements.logsFilterComponent.value],
          ["time_from", fromDateInput(elements.logsTimeFrom.value)],
          ["time_to", fromDateInput(elements.logsTimeTo.value)],
        ].forEach(([key, value]) => {
          if (value) params.set(key, value);
        });
        return params;
      }

      function buildEventsQuery(page) {
        const params = new URLSearchParams({ page: String(page), page_size: "50" });
        [
          ["project_id", elements.eventsFilterProject.value || state.projectId || ""],
          ["run_id", elements.eventsFilterRun.value],
          ["node_id", elements.eventsFilterNode.value],
          ["type", elements.eventsFilterType.value],
          ["time_from", fromDateInput(elements.eventsTimeFrom.value)],
          ["time_to", fromDateInput(elements.eventsTimeTo.value)],
        ].forEach(([key, value]) => {
          if (value) params.set(key, value);
        });
        return params;
      }

      function renderLogsPage(payload) {
        const items = (payload.items || []).filter((item) => matchesSearch(item, elements.logsSearch?.value || ""));
        elements.logsList.innerHTML = "";
        elements.logsSummary.textContent = `共 ${payload.total} 筆，篩選後 ${items.length} 筆，顯示第 ${payload.page} 頁。`;
        elements.logsPageLabel.textContent = `第 ${payload.page} 頁`;
        elements.logsPrev.disabled = payload.page <= 1;
        elements.logsNext.disabled = !payload.has_next;
        items.forEach((item) => {
          elements.logsList.appendChild(createTimelineItem(item));
        });
        if (!items.length) {
          elements.logsList.innerHTML = '<p class="empty-context">目前條件查無 log。</p>';
        }
      }

      function renderEventsPage(payload) {
        const items = (payload.items || []).filter((item) => matchesSearch(item, elements.eventsSearch?.value || ""));
        elements.eventsList.innerHTML = "";
        elements.eventsSummary.textContent = `共 ${payload.total} 筆，篩選後 ${items.length} 筆，顯示第 ${payload.page} 頁。`;
        elements.eventsPageLabel.textContent = `第 ${payload.page} 頁`;
        elements.eventsPrev.disabled = payload.page <= 1;
        elements.eventsNext.disabled = !payload.has_next;
        items.forEach((item) => {
          const card = createTimelineItem(item, { isEvent: true });
          const drilldown = document.createElement("div");
          drilldown.className = "log-item__actions";
          ["run_id", "node_id", "hook_id", "schedule_id", "job_id"].forEach((key) => {
            const value = item.drilldown && item.drilldown[key];
            if (!value) return;
            const button = document.createElement("button");
            button.type = "button";
            button.className = "secondary-btn";
            button.textContent = `前往 ${key.replace("_id", "")}：${value}`;
            button.addEventListener("click", async () => {
              if (item.project_id) {
                setProjectState(item.project_id);
                await loadContext();
              }
              navigateToRoute("chat");
              showToast(`已切換至 Chat，可依 ${key}=${value} 追蹤。`);
            });
            drilldown.appendChild(button);
          });
          card.querySelector(".logs-timeline-item__content")?.appendChild(drilldown);
          elements.eventsList.appendChild(card);
        });
        if (!items.length) {
          elements.eventsList.innerHTML = '<p class="empty-context">目前條件查無 event。</p>';
        }
      }

      async function copyVisibleLogsItems() {
        const payload = state.logsPage.latestLogsPayload || { items: [] };
        const text = getVisibleItemsText(payload, { keyword: elements.logsSearch?.value || "" });
        if (!text) {
          showToast("目前沒有可複製的 Logs 明細。", 7000, "warning");
          return;
        }
        await copyText(text, {
          toast: (message, options = {}) => showToast(message, options.duration || 7000, options.type || "success"),
          successMessage: "已複製目前 Logs 結果。",
          errorMessage: "複製失敗，請手動選取內容。",
        });
      }

      async function copyVisibleEventsItems() {
        const payload = state.logsPage.latestEventsPayload || { items: [] };
        const text = getVisibleItemsText(payload, { isEvent: true, keyword: elements.eventsSearch?.value || "" });
        if (!text) {
          showToast("目前沒有可複製的 Events 明細。", 7000, "warning");
          return;
        }
        await copyText(text, {
          toast: (message, options = {}) => showToast(message, options.duration || 7000, options.type || "success"),
          successMessage: "已複製目前 Events 結果。",
          errorMessage: "複製失敗，請手動選取內容。",
        });
      }

      async function loadLogsPage(page = 1) {
        const payload = await services.admin.getLogs(buildLogsQuery(page));
        state.logsPage.logsPage = payload.page;
        state.logsPage.logsHasNext = payload.has_next;
        state.logsPage.latestLogsPayload = payload;
        renderLogsPage(payload);
      }

      async function loadEventsPage(page = 1) {
        const payload = await services.admin.getEvents(buildEventsQuery(page));
        state.logsPage.eventsPage = payload.page;
        state.logsPage.eventsHasNext = payload.has_next;
        state.logsPage.latestEventsPayload = payload;
        renderEventsPage(payload);
      }

      function downloadLogsPayload() {
        const payload = state.logsPage.latestLogsPayload;
        if (!payload) {
          showToast("目前沒有可下載的 Logs 結果。", 8000, "warning");
          return;
        }
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `amon-logs-page-${payload.page || 1}.json`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      }

      async function loadLogsEventsPage() {
        if (!elements.logsFilterProject.value && state.projectId) {
          elements.logsFilterProject.value = state.projectId;
        }
        if (!elements.eventsFilterProject.value && state.projectId) {
          elements.eventsFilterProject.value = state.projectId;
        }
        setLogsEventsPanel("logs");
        setSeverityChipActive(elements.logsFilterSeverity.value || "");
        await Promise.all([loadLogsPage(1), loadEventsPage(1)]);
      }
      async function loadToolsSkillsPage() {
        const [toolsPayload, skillsPayload] = await Promise.all([
          services.admin.getToolsCatalog(state.projectId),
          services.admin.getSkillsCatalog(state.projectId),
        ]);
        state.toolsCatalog = toolsPayload.tools || [];
        state.skillsCatalog = skillsPayload.skills || [];
        state.toolsCatalogPolicyEditable = Boolean(toolsPayload.policy_editable);
        state.toolsCatalogUpdatedAt = toolsPayload.updated_at || "";
        state.skillsCatalogUpdatedAt = skillsPayload.updated_at || "";
        state.skillsCollisions = skillsPayload.collisions || [];
        ensureToolsSkillsSelection();
        renderToolsSkillsPage();
      }

      function formatRecentUsage(usage) {
        if (!usage || !usage.ts_ms) return "尚無紀錄";
        const dt = new Date(usage.ts_ms);
        return `${dt.toLocaleString("zh-TW", { hour12: false })} (${usage.decision || "unknown"})`;
      }

      function formatPolicyDecisionLabel(decision) {
        const normalized = String(decision || "deny").trim().toLowerCase();
        if (normalized === "allow") return "允許";
        if (normalized === "ask") return "需確認";
        if (normalized === "deny") return "拒絕";
        return normalized || "未知";
      }

      function formatToggleStateLabel(enabled) {
        return enabled ? "已啟用" : "已停用";
      }

      function formatRequireConfirmLabel(requireConfirm) {
        return requireConfirm ? "需要確認" : "可直接執行";
      }

      function normalizeSkillSourceLabel(source) {
        const normalized = String(source || "unknown").trim().toLowerCase();
        if (normalized === "project") return "專案";
        if (normalized === "global") return "全域";
        if (normalized === "builtin" || normalized === "built-in") return "內建";
        return source || "unknown";
      }

      function getSkillSourceIcon(source) {
        const normalized = String(source || "unknown").trim().toLowerCase();
        if (normalized === "project") return "folder_managed";
        if (normalized === "global") return "public";
        if (normalized === "builtin" || normalized === "built-in") return "deployed_code";
        return "school";
      }

      function formatToolGroupSubtitle(typeKey, toolCount) {
        const meta = TOOL_TYPE_META[typeKey] || TOOL_TYPE_META.unknown;
        const suffix = toolCount === 1 ? "method" : "methods";
        return `${meta.label} namespace · ${toolCount} ${suffix}`;
      }

      function renderSchema(schema) {
        return `<pre class="tools-codeblock">${escapeHtml(JSON.stringify(schema || {}, null, 2))}</pre>`;
      }

      function queueToolPolicyPlan(toolName, action, requireConfirm) {
        services.admin.planToolPolicy({ toolName, action, requireConfirm })
          .then((payload) => {
            showPlanCard({
              ...payload.plan,
              confirm_api: "/tools/policy/confirm",
            });
          })
          .catch((error) => showToast(`建立 Plan Card 失敗：${error.message}`));
      }

      function renderToolsSkillsPage() {
        syncToolsSkillsSummary({ collisions: state.skillsCollisions || [] });
        setToolsSkillsTab(toolsSkillsUi.activeTab);
        renderToolsFilterChips(state.toolsCatalog || []);
        renderSkillsSourceFilters(state.skillsCatalog || []);
        renderSkillTriggerOptions(state.skillsCatalog || []);
        renderToolsList(state.toolsCatalog || [], state.toolsCatalogPolicyEditable);
        renderSkillsList(state.skillsCatalog || [], state.skillsCollisions || []);
      }

      function renderToolsFilterChips(tools = []) {
        const options = buildToolFilterOptions(tools);
        elements.toolsFilterChips.innerHTML = options
          .map((item) => renderFilterChip({
            label: item.label,
            count: item.count,
            active: toolsSkillsUi.toolsFilter === item.key,
            dataset: `data-tools-filter="${escapeHtml(item.key)}"`,
          }))
          .join("");
      }

      function renderSkillsSourceFilters(skills = []) {
        const options = buildSkillsSourceOptions(skills);
        elements.skillsSourceFilters.innerHTML = options
          .map((item) => renderFilterChip({
            label: item.label,
            count: item.count,
            active: toolsSkillsUi.skillsSource === item.key,
            dataset: `data-skills-source="${escapeHtml(item.key)}"`,
          }))
          .join("");
      }

      function renderSkillTriggerOptions(skills = []) {
        const currentValue = elements.skillTriggerSelect.value;
        elements.skillTriggerSelect.innerHTML = "";
        skills.forEach((skill) => {
          const option = document.createElement("option");
          option.value = skill.name || "";
          option.textContent = `${skill.name || "(未命名)"} / ${skill.source || "unknown"}`;
          elements.skillTriggerSelect.appendChild(option);
        });
        if (!skills.length) {
          const option = document.createElement("option");
          option.value = "";
          option.textContent = "尚無可預覽的 skill";
          elements.skillTriggerSelect.appendChild(option);
        } else if (skills.some((skill) => skill.name === currentValue)) {
          elements.skillTriggerSelect.value = currentValue;
        }
        updateSkillsPreviewMeta();
      }

      function renderEmptyCatalog(title, description) {
        return `
          <article class="tools-empty-state">
            <span class="tools-empty-state__icon" aria-hidden="true">search_off</span>
            <strong>${escapeHtml(title)}</strong>
            <p>${escapeHtml(description)}</p>
          </article>
        `;
      }

      function renderToolsList(tools = [], policyEditable = false) {
        const query = toolsSkillsUi.search.trim().toLowerCase();
        const filteredTools = tools.filter((tool) => {
          const typeMatches = toolsSkillsUi.toolsFilter === "all" || normalizeToolType(tool.type) === toolsSkillsUi.toolsFilter;
          const searchMatches = !query || getToolSearchText(tool).includes(query);
          return typeMatches && searchMatches;
        });
        const groupMap = new Map();

        filteredTools.forEach((tool) => {
          const typeKey = normalizeToolType(tool.type);
          const groupLabel = extractToolGroupName(tool);
          const compositeKey = `${typeKey}::${groupLabel}`;
          if (!groupMap.has(compositeKey)) {
            groupMap.set(compositeKey, {
              typeKey,
              groupLabel,
              tools: [],
            });
          }
          groupMap.get(compositeKey).tools.push(tool);
        });

        elements.toolsListMeta.textContent = filteredTools.length
          ? `顯示 ${filteredTools.length} / ${tools.length} 個 tools`
          : `0 / ${tools.length} 個 tools 符合篩選`;

        if (!filteredTools.length) {
          elements.toolsList.innerHTML = renderEmptyCatalog("找不到符合條件的工具", "請調整搜尋關鍵字或切換類型篩選。");
          return;
        }

        elements.toolsList.innerHTML = Array.from(groupMap.values())
          .sort((a, b) => `${a.groupLabel}.${a.typeKey}`.localeCompare(`${b.groupLabel}.${b.typeKey}`))
          .map(({ typeKey, groupLabel, tools: groupedTools }) => {
            const meta = TOOL_TYPE_META[typeKey] || TOOL_TYPE_META.unknown;
            const sampleMethods = groupedTools
              .slice(0, 4)
              .map((tool) => `<span class="tool-group__method-pill">${escapeHtml(extractToolMethodName(tool.name))}</span>`)
              .join("");
            return `
              <details class="tool-group" open data-tool-group-type="${escapeHtml(typeKey)}">
                <summary class="tool-group__summary">
                  <span class="tool-group__summary-main">
                    <span class="tool-group__icon" aria-hidden="true">${meta.icon}</span>
                    <span class="tool-group__identity">
                      <strong>${escapeHtml(groupLabel)}</strong>
                      <span>${escapeHtml(formatToolGroupSubtitle(typeKey, groupedTools.length))}</span>
                      <span class="tool-group__method-list">${sampleMethods}</span>
                    </span>
                  </span>
                  <span class="tool-group__summary-meta">
                    <span class="tool-group__scope tool-group__scope--${escapeHtml(meta.tone)}">${escapeHtml(meta.label)}</span>
                    <span class="tool-group__count">${groupedTools.length}</span>
                  </span>
                </summary>
                <div class="tool-group__body">
                  ${groupedTools
                    .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
                    .map((tool) => {
                      const risk = String(tool.risk || "unknown").toLowerCase();
                      const allowPaths = (tool.allowed_paths || []).join(", ") || "workspace";
                      const rawName = String(tool.name || "");
                      const separator = rawName.includes(":") ? ":" : ".";
                      const rawParts = rawName.split(separator);
                      const methodPrefix = rawParts.length > 1 ? `${rawParts.slice(0, -1).join(separator)}${separator}` : "";
                      return `
                        <details class="tool-method">
                          <summary class="tool-method__summary">
                            <span class="tool-method__summary-main">
                              <span class="tool-method__name">
                                ${methodPrefix ? `<span class="tool-method__prefix">${escapeHtml(methodPrefix)}</span>` : ""}
                                <strong>${escapeHtml(extractToolMethodName(rawName))}</strong>
                              </span>
                            </span>
                            <span class="tool-method__summary-meta">
                              <span class="risk-chip risk-chip--${escapeHtml(risk)}">risk: ${escapeHtml(risk)}</span>
                            </span>
                          </summary>
                          <div class="tool-method__body">
                            <div class="tool-method__info-grid">
                              <article class="tool-method__info-card">
                                <span class="tool-method__info-label">類型</span>
                                <strong>${escapeHtml(meta.label)}</strong>
                              </article>
                              <article class="tool-method__info-card">
                                <span class="tool-method__info-label">版本</span>
                                <strong>${escapeHtml(String(tool.version || "unknown"))}</strong>
                              </article>
                              <article class="tool-method__info-card">
                                <span class="tool-method__info-label">允許路徑</span>
                                <strong>${escapeHtml(allowPaths)}</strong>
                              </article>
                              <article class="tool-method__info-card">
                                <span class="tool-method__info-label">最近使用</span>
                                <strong>${escapeHtml(formatRecentUsage(tool.recent_usage))}</strong>
                              </article>
                              <article class="tool-method__info-card">
                                <span class="tool-method__info-label">啟用狀態</span>
                                <strong>${escapeHtml(formatToggleStateLabel(Boolean(tool.enabled)))}</strong>
                              </article>
                              <article class="tool-method__info-card">
                                <span class="tool-method__info-label">執行門檻</span>
                                <strong>${escapeHtml(formatRequireConfirmLabel(Boolean(tool.require_confirm)))}</strong>
                              </article>
                            </div>
                            <p class="tool-method__policy-note"><strong>策略說明：</strong>${escapeHtml(tool.policy_reason || "未命中 allow 規則，預設拒絕")}</p>
                            <p class="tool-method__policy"><strong>預設策略：</strong>${escapeHtml(formatPolicyDecisionLabel(tool.policy_decision))}</p>
                            <div class="tool-method__schema-stack">
                              <details class="tool-method__schema-panel">
                                <summary>輸入 schema</summary>
                                ${renderSchema(tool.input_schema)}
                              </details>
                              <details class="tool-method__schema-panel">
                                <summary>輸出 schema</summary>
                                ${renderSchema(tool.output_schema)}
                              </details>
                            </div>
                            <div class="tool-card__actions">
                              ${policyEditable
                                ? `
                                  <button
                                    type="button"
                                    class="btn btn--secondary secondary-btn small"
                                    data-tool-action="toggle-enabled"
                                    data-tool-name="${escapeHtml(tool.name)}"
                                    data-tool-enabled="${tool.enabled ? "true" : "false"}"
                                    data-tool-require-confirm="${tool.require_confirm ? "true" : "false"}"
                                  >${tool.enabled ? "停用" : "啟用"}</button>
                                  <button
                                    type="button"
                                    class="btn btn--ghost secondary-btn small"
                                    data-tool-action="toggle-confirm"
                                    data-tool-name="${escapeHtml(tool.name)}"
                                    data-tool-enabled="${tool.enabled ? "true" : "false"}"
                                    data-tool-require-confirm="${tool.require_confirm ? "true" : "false"}"
                                  >執行前確認：${tool.require_confirm ? "開" : "關"}</button>
                                `
                                : `<span class="tool-method__readonly">目前策略為唯讀模式</span>`}
                            </div>
                          </div>
                        </details>
                      `;
                    })
                    .join("")}
                </div>
              </details>
            `;
          })
          .join("");
      }

      function renderSkillsList(skills = [], collisions = []) {
        const query = toolsSkillsUi.search.trim().toLowerCase();
        const filteredSkills = skills.filter((skill) => {
          const source = String(skill.source || "unknown");
          const sourceMatches = toolsSkillsUi.skillsSource === "all" || source === toolsSkillsUi.skillsSource;
          const searchMatches = !query || getSkillSearchText(skill).includes(query);
          return sourceMatches && searchMatches;
        });

        elements.skillsListMeta.textContent = filteredSkills.length
          ? `顯示 ${filteredSkills.length} / ${skills.length} 個 skills`
          : `0 / ${skills.length} 個 skills 符合篩選`;
        elements.skillsList.classList.toggle("skills-list--grid", toolsSkillsUi.skillsView === "grid");
        elements.skillsList.classList.toggle("skills-list--list", toolsSkillsUi.skillsView === "list");
        elements.skillsViewGrid.classList.toggle("is-active", toolsSkillsUi.skillsView === "grid");
        elements.skillsViewList.classList.toggle("is-active", toolsSkillsUi.skillsView === "list");
        elements.skillsViewGrid.setAttribute("aria-pressed", String(toolsSkillsUi.skillsView === "grid"));
        elements.skillsViewList.setAttribute("aria-pressed", String(toolsSkillsUi.skillsView === "list"));

        elements.skillsCollisions.innerHTML = collisions.length
          ? collisions
            .map((item) => `
              <article class="collision-tip">
                <strong>${escapeHtml(item.name)}</strong>
                <span>${escapeHtml(item.message)}</span>
              </article>
            `)
            .join("")
          : "";

        if (!filteredSkills.length) {
          elements.skillsList.innerHTML = renderEmptyCatalog("找不到符合條件的 skill", "請調整搜尋關鍵字、來源篩選，或確認是否已執行 skills scan。");
          return;
        }

        elements.skillsList.innerHTML = filteredSkills
          .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
          .map((skill) => {
            const frontmatter = skill.frontmatter || {};
            const source = String(skill.source || "unknown");
            const sourceLabel = normalizeSkillSourceLabel(source);
            const description = frontmatter.description || skill.description || "無描述";
            const definition = {
              name: frontmatter.name || skill.name,
              description,
              source,
              path: skill.path || "",
            };
            return `
              <details class="skill-card skill-card--${escapeHtml(toolsSkillsUi.skillsView)}" data-skill-source="${escapeHtml(source)}">
                <summary class="skill-card__summary">
                  <span class="skill-card__summary-main">
                    <span class="skill-card__icon" aria-hidden="true">${getSkillSourceIcon(source)}</span>
                    <span class="skill-card__body">
                      <span class="skill-card__title-row">
                        <strong>${escapeHtml(skill.name || "(未命名)")}</strong>
                        <span class="skill-card__source">${escapeHtml(source)}</span>
                      </span>
                      <span class="skill-card__desc">${escapeHtml(description)}</span>
                      <span class="skill-card__path">${escapeHtml(skill.path || "")}</span>
                    </span>
                  </span>
                </summary>
                <div class="skill-card__detail">
                  <div class="skill-card__detail-grid">
                    <article class="skill-card__detail-card">
                      <span class="tool-method__info-label">來源</span>
                      <strong>${escapeHtml(sourceLabel)}</strong>
                    </article>
                    <article class="skill-card__detail-card">
                      <span class="tool-method__info-label">觸發名稱</span>
                      <strong>${escapeHtml(skill.name || "(未命名)")}</strong>
                    </article>
                    <article class="skill-card__detail-card">
                      <span class="tool-method__info-label">Frontmatter 名稱</span>
                      <strong>${escapeHtml(frontmatter.name || skill.name || "(未命名)")}</strong>
                    </article>
                    <article class="skill-card__detail-card">
                      <span class="tool-method__info-label">檔案位置</span>
                      <strong class="skill-card__path-value">${escapeHtml(skill.path || "未提供")}</strong>
                    </article>
                  </div>
                  <p class="skill-card__detail-copy">${escapeHtml(description)}</p>
                  <div class="skill-card__definition">
                    <span class="tool-method__info-label">Skill Definition</span>
                    ${renderSchema(definition)}
                  </div>
                </div>
              </details>
            `;
          })
          .join("");
      }

      function updateSkillsPreviewMeta() {
        const selectedOption = elements.skillTriggerSelect.selectedOptions?.[0];
        elements.skillsPreviewMeta.textContent = selectedOption
          ? `目前選擇：${selectedOption.textContent}`
          : "請先選一個 skill。";
      }

      function showToast(message, duration = 9000, type = "info") {
        toastManager.show(message, { duration, type });
      }

      window.amonUiDebug = {
        showToast,
        showConfirmModal: (options) => confirmModal.open(options),
      };

      function renderStoreSummary(storeState) {
        const runStatusRaw = storeState.run?.status || (state.streaming ? "running" : "idle");
        const runStatus = formatUnknownValue(runStatusRaw, t("status.run.idle"));
        const runProgress = storeState.run?.progress;
        if (!elements.cardRunProgress || !elements.cardBilling || !elements.cardPendingConfirmations) {
          return;
        }
        const runStatusLabel = t(statusToI18nKey("run", runStatusRaw, "status.run.idle"), runStatus);
        const totalCost = Number(storeState.billing.total_cost || 0);
        const pendingJobs = Object.values(storeState.jobs).filter((job) => job.status && job.status !== "completed").length;

        appStore.patch({
          layout: {
            ...(appStore.getState().layout || {}),
            runPill: {
              text: `Run：${runStatusLabel}`,
              level: mapRunStatusLevel(runStatusRaw),
              title: `目前執行狀態：${runStatusLabel}`,
            },
            budgetPill: `Budget：NT$ ${totalCost.toFixed(2)} / NT$ 5,000`,
          },
        });

        elements.cardRunProgress.textContent = Number.isFinite(runProgress) ? `${runProgress}%` : "尚未有 Run";
        elements.cardRunProgress.title = Number.isFinite(runProgress) ? "目前 Run 進度" : "尚未有 Run 可顯示進度";
        elements.cardBilling.textContent = `NT$ ${totalCost.toFixed(2)}`;
        elements.cardBilling.title = "目前已累計費用";
        elements.cardPendingConfirmations.textContent = pendingJobs > 0 ? `${pendingJobs} 項任務進行中` : "0 項";
        elements.cardPendingConfirmations.title = pendingJobs > 0 ? "仍有任務等待確認或完成" : "目前沒有待確認任務";
      }

      state.uiStore.subscribe((snapshot) => {
        renderStoreSummary(snapshot);
        if (snapshot.docs.length > 0) {
          renderDocs(snapshot.docs);
        }
        if (Array.isArray(snapshot.artifacts) && snapshot.artifacts.length > 0) {
          state.runArtifacts = snapshot.artifacts.filter((artifact) => !isConversationArtifact(artifact));
          renderArtifactsInspector(state.runArtifacts);
        }
      });
      renderStoreSummary(state.uiStore.getState());

      function appendMessage(role, text, meta = {}) {
        const row = document.createElement("article");
        row.className = "timeline-row";

        const bubble = document.createElement("div");
        bubble.className = `chat-bubble ${role}`;
        bubble.innerHTML = renderMarkdown(text);

        const footer = document.createElement("footer");
        footer.className = "timeline-meta";
        const roleLabel = role === "user" ? "你" : "Amon";
        const status = meta.status ? `・${meta.status}` : "";
        footer.textContent = `${new Date().toLocaleTimeString("zh-TW", { hour12: false })}・${roleLabel}${status}`;

        row.appendChild(bubble);
        row.appendChild(footer);
        elements.timeline.appendChild(row);
        elements.timeline.scrollTop = elements.timeline.scrollHeight;
        return bubble;
      }

      function appendTimelineStatus(message) {
        const item = document.createElement("div");
        item.className = "timeline-status";
        item.textContent = message;
        elements.timeline.appendChild(item);
        elements.timeline.scrollTop = elements.timeline.scrollHeight;
      }

      function executionStatusMeta(status = "pending") {
        if (status === "succeeded") return { icon: "✅", label: "已完成" };
        if (status === "running") return { icon: "🔄", label: "執行中" };
        if (status === "failed") return { icon: "❌", label: "失敗" };
        return { icon: "⚪", label: "等待中" };
      }

      function updateExecutionStep(stepId, next = {}) {
        const current = state.executionTimeline.get(stepId) || {};
        state.executionTimeline.set(stepId, {
          id: stepId,
          title: next.title || current.title || stepId,
          status: next.status || current.status || "pending",
          details: next.details || current.details || "",
          inferred: next.inferred !== undefined ? next.inferred : current.inferred || false,
          updatedAt: new Date().toISOString(),
        });
        renderExecutionTimeline();
      }

      function renderExecutionTimeline() {
        if (!elements.executionAccordion) return;
        const items = Array.from(state.executionTimeline.values());
        if (!items.length) {
          elements.executionAccordion.innerHTML = '<p class="empty-context">尚無執行步驟。</p>';
          return;
        }
        elements.executionAccordion.innerHTML = "";
        items.forEach((item) => {
          const statusMeta = executionStatusMeta(item.status);
          const details = document.createElement("details");
          details.className = `execution-step execution-step--${item.status}`;
          details.open = item.status === "running";
          details.innerHTML = `
            <summary>${statusMeta.icon} ${escapeHtml(item.title)} <span>${statusMeta.label}</span></summary>
            <div class="execution-step__body">
              <p>${escapeHtml(item.details || "尚無詳細資訊")}</p>
              <small>${item.inferred ? "推測來源（非結構化）" : "結構化事件"} · ${new Date(item.updatedAt).toLocaleTimeString("zh-TW", { hour12: false })}</small>
            </div>
          `;
          elements.executionAccordion.appendChild(details);
        });
      }

      function applyExecutionEvent(eventType, data = {}) {
        if (eventType === "token") {
          updateExecutionStep("thinking", { title: "Thinking", status: "running", details: "模型正在輸出 token", inferred: false });
          return;
        }
        if (eventType === "plan") {
          updateExecutionStep("planning", { title: "Planning", status: "running", details: "已產生 Plan Card，等待確認", inferred: false });
          return;
        }
        if (eventType === "result") {
          updateExecutionStep("tool_execution", { title: "Tool execution", status: "succeeded", details: "工具呼叫已回傳結果", inferred: false });
          return;
        }
        if (eventType === "done") {
          updateExecutionStep("thinking", { title: "Thinking", status: "succeeded", details: `流程完成（${data.status || "ok"}）`, inferred: false });
          updateExecutionStep("planning", { title: "Planning", status: data.status === "confirm_required" ? "running" : "succeeded", details: data.status === "confirm_required" ? "等待使用者確認" : "規劃流程已完成", inferred: false });
          updateExecutionStep("node_status", { title: "Node 狀態", status: data.status === "ok" ? "succeeded" : "running", details: state.graphRunId ? `Run ${shortenId(state.graphRunId)} 已更新` : "等待下一次 上下文刷新", inferred: true });
          return;
        }
        if (eventType === "error") {
          updateExecutionStep("tool_execution", { title: "Tool execution", status: "failed", details: data.message || "執行時發生錯誤", inferred: false });
        }
      }

      function normalizeHistoryTimestamp(ts = "") {
        const rawValue = String(ts || "").trim();
        if (!rawValue) return "";
        const parsed = new Date(rawValue);
        if (Number.isNaN(parsed.getTime())) {
          return rawValue;
        }
        return parsed.toLocaleTimeString("zh-TW", { hour12: false });
      }

      function appendRestoredMessage(role, text, ts = "") {
        const normalizedText = String(text || "");
        const timestampText = normalizeHistoryTimestamp(ts);
        if (typeof CHAT_VIEW.__chatAppendMessage === "function") {
          CHAT_VIEW.__chatAppendMessage(role, normalizedText, { timestampText });
          return;
        }

        const row = document.createElement("article");
        row.className = `chat-msg chat-msg--${role}`;

        const bubble = document.createElement("div");
        bubble.className = `chat-msg__bubble chat-msg__bubble--${role}`;
        const bubbleBody = document.createElement("div");
        bubbleBody.className = "chat-msg__body";
        bubbleBody.innerHTML = renderMarkdown(normalizedText);
        bubble.appendChild(bubbleBody);
        row.appendChild(bubble);

        const footer = document.createElement("footer");
        footer.className = "chat-msg__meta";
        const timestamp = document.createElement("time");
        timestamp.className = "chat-msg__timestamp";
        timestamp.textContent = timestampText || new Date().toLocaleTimeString("zh-TW", { hour12: false });
        footer.appendChild(timestamp);
        row.appendChild(footer);

        elements.timeline.appendChild(row);
      }

      async function downloadProjectHistory() {
        if (!state.projectId) {
          showToast("請先選擇專案後再下載對話紀錄。", 9000, "warning");
          return;
        }
        const payload = await services.threads.getProjectThreadHistory(state.projectId, state.activeThreadId || "");
        const fileName = `thread-history-${state.projectId}.json`;
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = fileName;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
      }

      function beginProjectHydration() {
        state.pendingProjectLoadToken += 1;
        return state.pendingProjectLoadToken;
      }

      function isCurrentProjectHydrationToken(token) {
        return token === state.pendingProjectLoadToken;
      }

      async function loadProjectHistory(token = state.pendingProjectLoadToken) {
        if (!isCurrentProjectHydrationToken(token)) return;
        elements.timeline.innerHTML = "";
        if (!state.projectId) {
          appendTimelineStatus("目前為無專案模式。輸入任務後會自動建立新專案並切換。");
          return;
        }
        renderRollupPreview();
        const payload = await services.threads.getProjectThreadHistory(state.projectId, state.activeThreadId || "");
        if (!isCurrentProjectHydrationToken(token)) return;
        state.activeThreadId = payload.thread_id || null;
        if (state.projectId && state.activeThreadId) {
          state.activeThreadByProject[state.projectId] = state.activeThreadId;
        }
        state.threadList = (state.threadList || []).map((thread) => ({
          ...thread,
          is_active: String(thread.thread_id || "").trim() === String(state.activeThreadId || "").trim(),
        }));
        renderThreadList();
        const messages = Array.isArray(payload.messages) ? payload.messages : [];
        if (!messages.length) {
          appendTimelineStatus("目前尚無歷史對話。請直接輸入需求開始。");
          return;
        }
        messages.forEach((item) => {
          if (item.role === "status") {
            const text = String(item.text || "").trim();
            if (!text) return;
            appendTimelineStatus(text);
            return;
          }
          const role = item.role === "user" ? "user" : "agent";
          const text = String(item.text || "").trim();
          if (!text) return;
          appendRestoredMessage(role, text, item.ts || "");
        });
        elements.timeline.scrollTop = elements.timeline.scrollHeight;
      }

      function escapeHtml(text) {
        return text
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }

      function renderInlineMarkdown(text) {
        let html = escapeHtml(text);
        html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
        html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
        html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
        html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        return html;
      }

      function renderMarkdown(text) {
        const source = String(text || "");
        if (window.marked?.parse) {
          marked.setOptions({
            breaks: true,
            gfm: true,
            highlight(code, lang) {
              if (window.hljs) {
                if (lang && hljs.getLanguage(lang)) {
                  return hljs.highlight(code, { language: lang }).value;
                }
                return hljs.highlightAuto(code).value;
              }
              return escapeHtml(code);
            },
          });
          const rendered = marked.parse(source);
          return window.DOMPurify ? window.DOMPurify.sanitize(rendered) : rendered;
        }
        return `<p>${renderInlineMarkdown(source).replaceAll("\n", "<br />")}</p>`;
      }

      function highlightPreviewBlocks(root = elements.docsPreviewContent) {
        if (!window.hljs || !root) return;
        root.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
      }

      function setStreaming(active) {

        state.streaming = active;
        elements.streamProgress.hidden = !active;
        elements.chatInput.disabled = false;
      }

      function resetPlanCard() {
        state.plan = null;
        elements.planCard.hidden = true;
        elements.planContent.textContent = "";
        elements.planCommands.innerHTML = "";
        elements.planPatches.innerHTML = "";
        elements.planRisk.innerHTML = "";
      }

      function formatPlanListItem(item) {
        if (typeof item === "string") {
          return item;
        }
        if (item == null) {
          return "";
        }
        if (typeof item !== "object") {
          return String(item);
        }
        const action = String(item.action || "").trim();
        const target = String(item.target || item.path || "").trim();
        const detail = String(item.detail || "").trim();
        if (action && target) {
          return detail ? `${action} ${target} (${detail})` : `${action} ${target}`;
        }
        if (action) {
          return detail ? `${action} (${detail})` : action;
        }
        if (target) {
          return detail ? `${target} (${detail})` : target;
        }
        return JSON.stringify(item, null, 2);
      }

      function renderPlanList(container, items = []) {
        if (!container) return;
        container.innerHTML = "";
        const normalizedItems = Array.isArray(items) ? items : [];
        if (!normalizedItems.length) {
          const emptyItem = document.createElement("li");
          emptyItem.textContent = "無";
          container.appendChild(emptyItem);
          return;
        }
        normalizedItems.forEach((item) => {
          const row = document.createElement("li");
          row.textContent = formatPlanListItem(item);
          container.appendChild(row);
        });
      }

      function renderPlanRisk(plan = {}) {
        if (!elements.planRisk) return;
        elements.planRisk.innerHTML = "";
        const risk = plan?.risk && typeof plan.risk === "object" ? plan.risk : {};
        const level = String(risk.level || plan.risk || "").trim().toLowerCase();
        const levelTone = ["low", "medium", "high"].includes(level) ? level : "unknown";
        const badges = [];
        if (level) {
          badges.push(`<span class="risk-chip risk-chip--${escapeHtml(levelTone)}">risk: ${escapeHtml(level)}</span>`);
        }
        if (risk.scope) {
          badges.push(`<span class="pill pill--neutral">scope: ${escapeHtml(String(risk.scope))}</span>`);
        }
        if (Object.prototype.hasOwnProperty.call(risk, "require_confirm")) {
          badges.push(`<span class="pill ${risk.require_confirm ? "pill--warn" : "pill--success"}">${risk.require_confirm ? "需要確認" : "無需確認"}</span>`);
        }
        elements.planRisk.innerHTML = badges.join("");
      }

      function setProjectState(projectId) {
        const previousProjectId = normalizeProjectIdForUi(state.projectId);
        if (previousProjectId) {
          state.activeThreadByProject[previousProjectId] = state.activeThreadId;
        }
        const nextProjectId = normalizeProjectIdForUi(projectId) || null;
        if (state.projectId !== nextProjectId) {
          state.activeThreadId = String(state.activeThreadByProject[nextProjectId] || "").trim() || null;
          state.threadList = [...(state.threadsByProject[nextProjectId] || [])];
        }
        state.projectId = nextProjectId;
        const layoutState = appStore.getState().layout || {};
        appStore.patch({
          layout: {
            ...layoutState,
            projectId: state.projectId,
          },
        });
        elements.refreshContext.disabled = !state.projectId;
        rememberExpandedProject(state.projectId);
        if (state.projectId && !elements.projectSelect.querySelector(`option[value="${CSS.escape(state.projectId)}"]`)) {
          const dynamicOption = document.createElement("option");
          dynamicOption.value = state.projectId;
          dynamicOption.textContent = "新專案";
          dynamicOption.title = `ID: ${state.projectId}`;
          dynamicOption.dataset.dynamic = "true";
          elements.projectSelect.appendChild(dynamicOption);
        }
        elements.projectSelect.value = nextProjectId || "";
        syncContextHeader();
        renderThreadList();
        refreshContextDraftUi();
        if (!state.projectId) {
          state.activeThreadId = null;
          state.threadList = [];
          state.graphRunId = null;
          state.graph = null;
          state.graphNodeStates = {};
          state.graphEvents = [];
          state.runArtifacts = [];
          state.artifactPreviewItem = null;
          elements.timeline.innerHTML = "";
          renderArtifactsInspector([]);
          elements.graphPreview.innerHTML = "<p class=\"empty-context\">請先在上方選擇專案。</p>";
          elements.graphCode.textContent = "";
          elements.contextOverview.textContent = "請先在上方選擇專案，右側內容會自動同步。";
          elements.graphRunMeta.textContent = "尚未偵測到 Run";
          elements.copyRunId.disabled = true;
        }
      }

      async function recoverFromMissingProject(error, options = {}) {
        const { source } = options;
        const failedProjectId = String(state.projectId || "").trim();
        logUiDebug("project.missing", {
          source: source || "unknown",
          project_id: failedProjectId || null,
          message: String(error?.message || error || ""),
        });
        setProjectState(null);
        await loadProjects();
        showToast(
          failedProjectId
            ? `目前專案 ${failedProjectId} 已不存在，已清除失效狀態。`
            : `目前專案已不存在，已清除失效狀態。`,
          9000,
          "warning",
        );
      }

      function syncContextHeader() {
        const selected = getProjectLabel();
        elements.contextProject.textContent = `目前專案：${selected}`;
        elements.chatProjectLabel.textContent = `目前專案：${selected}`;
        if (elements.sidebarProjectName) {
          elements.sidebarProjectName.textContent = selected;
        }
      }

      function openInspectorPanel(tabName = "thinking") {
        const layoutState = appStore.getState().layout || {};
        const inspector = layoutState.inspector || {};
        const nextInspector = {
          ...inspector,
          activeTab: tabName,
        };

        if (window.innerWidth <= 1200) {
          appStore.patch({
            layout: {
              ...layoutState,
              inspector: nextInspector,
            },
          });
          elements.uiShell?.classList.add("is-context-drawer-open");
          return;
        }

        if (!inspector.collapsed && inspector.activeTab === tabName) return;
        appStore.patch({
          layout: {
            ...layoutState,
            inspector: {
              ...nextInspector,
              collapsed: false,
            },
          },
        });
      }

      function focusInspectorSection(which) {
        const sectionMap = {
          execution: elements.inspectorExecution,
          thinking: elements.inspectorThinking,
          artifacts: elements.inspectorArtifacts,
        };
        openInspectorPanel(which);
        const target = sectionMap[which] || elements.inspectorThinking;
        if (!target) return;
        requestAnimationFrame(() => {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          if (typeof target.focus === "function") {
            target.focus({ preventScroll: true });
          }
        });
      }

      function refreshContextDraftUi() {
        const draftKey = getContextDraftStorageKey();
        const draftText = readStorage(draftKey) || "";
        elements.contextDraftInput.value = draftText;
        if (draftText.trim()) {
          elements.contextDraftMeta.textContent = state.projectId
            ? "已載入目前專案的本機草稿。"
            : "已載入未綁定專案的本機草稿。";
        } else {
          elements.contextDraftMeta.textContent = "尚未儲存草稿。";
        }
      }

      function saveContextDraft() {
        const text = (elements.contextDraftInput.value || "").trim();
        const draftKey = getContextDraftStorageKey();
        writeStorage(draftKey, text);
        elements.contextDraftMeta.textContent = text
          ? `已儲存本機草稿（${new Date().toLocaleString("zh-TW")})。`
          : "草稿為空，已清空本機草稿。";
        showToast(text ? "上下文草稿已儲存（僅本機）。" : "已清空本機草稿。", 9000, "success");
      }

      async function clearContextDraft(scope = "chat") {
        const title = scope === "project" ? "清空專案上下文草稿" : "清空本次對話上下文草稿";
        const description = scope === "project"
          ? "將刪除目前專案在此瀏覽器的 上下文草稿。此動作只影響本機，不會刪除伺服器資料，且不可復原。"
          : "將刪除目前對話在此瀏覽器的 上下文草稿。此動作只影響本機，不會刪除伺服器資料，且不可復原。";
        const confirmed = await confirmModal.open({
          title,
          description,
          confirmText: "確認清空",
          cancelText: "取消",
        });
        if (!confirmed) {
          showToast("已取消清空上下文。", 5000, "neutral");
          return;
        }
        const key = getContextDraftStorageKey(scope === "project" ? state.projectId : null);
        removeStorage(key);
        if (scope === "project") {
          refreshContextDraftUi();
        } else {
          elements.contextDraftInput.value = "";
          elements.contextDraftMeta.textContent = "已清空本次對話上下文草稿。";
        }
        showToast("已清空上下文草稿（僅本機）。", 9000, "success");
      }

      function importContextDraftFromFile(file) {
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
          elements.contextDraftInput.value = String(reader.result || "");
          elements.contextDraftMeta.textContent = `已匯入檔案：${file.name}`;
          showToast(`已匯入 ${file.name}，請記得儲存草稿。`, 9000, "success");
        };
        reader.onerror = () => {
          showToast("檔案匯入失敗，請確認檔案格式是否正確。", 9000, "danger");
        };
        reader.readAsText(file);
      }

      function extractContextFromChat() {
        const latestUser = [...elements.timeline.querySelectorAll(".chat-bubble.user")].pop();
        if (!latestUser) {
          showToast("目前沒有可擷取的對話內容。", 9000, "warning");
          return;
        }
        const text = latestUser.textContent.replace(/^你：/, "").trim();
        elements.contextDraftInput.value = text;
        elements.contextDraftMeta.textContent = "已帶入最近一則使用者對話，請檢查後儲存。";
        showToast("已從最近對話擷取 上下文草稿。", 9000, "success");
      }

      function renderRunMeta(runId, runStatus) {
        if (!runId) {
          elements.graphRunMeta.textContent = "尚未偵測到 Run";
          elements.graphRunMeta.title = "尚未有可用 Run。";
          elements.copyRunId.disabled = true;
          return;
        }
        const shortRunId = shortenId(runId);
        const safeStatus = formatUnknownValue(runStatus, "尚未取得狀態");
        elements.graphRunMeta.textContent = `Run：${shortRunId}（${safeStatus}）`;
        elements.graphRunMeta.title = `完整 Run ID：${runId}`;
        elements.copyRunId.disabled = false;
        elements.copyRunId.dataset.runId = runId;
      }

      function normalizeProjectRecord(project = {}) {
        if (!project || typeof project !== "object") return null;
        const projectId = project.project_id || project.id || "";
        if (!projectId) return null;
        return {
          ...project,
          project_id: projectId,
          name: project.name || project.title || projectId,
          created_at: String(project.created_at || "").trim(),
          updated_at: String(project.updated_at || "").trim(),
        };
      }

      function sortProjectsForDisplay(projects = []) {
        return [...projects].sort((a, b) => {
          const updatedDiff = toSortableTimestamp(b.updated_at) - toSortableTimestamp(a.updated_at);
          if (updatedDiff !== 0) return updatedDiff;
          const createdDiff = toSortableTimestamp(b.created_at) - toSortableTimestamp(a.created_at);
          if (createdDiff !== 0) return createdDiff;
          return String(a.name || a.project_id || "").localeCompare(String(b.name || b.project_id || ""));
        });
      }

      function normalizeThreadRecord(thread = {}) {
        const threadId = String(thread.thread_id || thread.id || "").trim();
        if (!threadId) return null;
        const title = String(thread.title || "").trim() || `Thread ${threadId}`;
        return {
          thread_id: threadId,
          title,
          created_at: String(thread.created_at || "").trim(),
          updated_at: String(thread.updated_at || "").trim(),
          is_active: Boolean(thread.is_active),
        };
      }

      function toSortableTimestamp(value = "") {
        const parsed = Date.parse(String(value || "").trim());
        return Number.isNaN(parsed) ? 0 : parsed;
      }

      function formatThreadUpdatedAt(value = "") {
        const raw = String(value || "").trim();
        if (!raw) return "尚未更新";
        const parsed = new Date(raw);
        if (Number.isNaN(parsed.getTime())) return raw;
        return parsed.toLocaleString("zh-TW", { hour12: false });
      }

      function renderProjectSelectOptions(projects = []) {
        if (!elements.projectSelect) return;
        const currentValue = String(state.projectId || "").trim();
        elements.projectSelect.innerHTML = "";

        const emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "無專案";
        elements.projectSelect.appendChild(emptyOption);

        sortProjectsForDisplay(projects).forEach((project) => {
          const option = document.createElement("option");
          option.value = String(project.project_id || "").trim();
          option.textContent = String(project.name || project.project_id || "未命名專案");
          option.title = `ID: ${option.value}`;
          elements.projectSelect.appendChild(option);
        });

        elements.projectSelect.value = currentValue || "";
      }

      function sortThreadsForDisplay(threads = []) {
        return [...threads].sort((a, b) => {
          const updatedDiff = toSortableTimestamp(b.updated_at) - toSortableTimestamp(a.updated_at);
          if (updatedDiff !== 0) return updatedDiff;
          const createdDiff = toSortableTimestamp(b.created_at) - toSortableTimestamp(a.created_at);
          if (createdDiff !== 0) return createdDiff;
          return String(a.thread_id || "").localeCompare(String(b.thread_id || ""));
        });
      }

      function renderThreadList() {
        if (!elements.threadList) return;
        elements.createThreadBtn.disabled = !state.projectId;
        const activeProjectId = String(state.projectId || "").trim();
        const projects = getKnownProjects();
        if (!projects.length) {
          elements.threadList.innerHTML = '<p class="thread-tree__empty">目前尚無專案。</p>';
          return;
        }
        const fragment = document.createDocumentFragment();
        projects.forEach((project) => {
          const projectId = String(project.project_id || "").trim();
          if (!projectId) return;
          const isActiveProject = projectId === activeProjectId;
          const isExpanded = isActiveProject || projectTreeUi.expandedProjectIds.has(projectId);
          const branch = document.createElement("section");
          const branchDomId = `project-threads-${toProjectDomId(projectId)}`;
          const cachedThreads = sortThreadsForDisplay(
            isActiveProject ? state.threadList || [] : state.threadsByProject[projectId] || []
          );
          const hasCachedThreads = cachedThreads.length > 0;
          const branchMeta = isActiveProject
            ? `目前專案${hasCachedThreads ? ` · ${cachedThreads.length} 個對話串` : ""}`
            : hasCachedThreads
              ? `${cachedThreads.length} 個對話串`
              : "";

          branch.className = "project-branch";
          branch.classList.toggle("is-active", isActiveProject);
          branch.classList.toggle("is-expanded", isExpanded);

          const toggle = document.createElement("button");
          toggle.type = "button";
          toggle.className = "project-branch__toggle";
          toggle.dataset.projectId = projectId;
          toggle.setAttribute("aria-expanded", String(isExpanded));
          toggle.setAttribute("aria-controls", branchDomId);
          toggle.innerHTML = `
            <span class="project-branch__toggle-main">
              <span class="project-branch__chevron" aria-hidden="true">▶</span>
              <span class="project-branch__folder" aria-hidden="true">folder</span>
              <span class="project-branch__title-group">
                <strong class="project-branch__title">${escapeHtml(String(project.name || projectId))}</strong>
                ${branchMeta ? `<span class="project-branch__meta">${escapeHtml(branchMeta)}</span>` : ""}
              </span>
            </span>
            ${isActiveProject ? '<span class="project-branch__badge">目前</span>' : ""}
          `;
          toggle.addEventListener("click", async () => {
            if (!isActiveProject) {
              rememberExpandedProject(projectId);
              renderThreadList();
              await activateProject(projectId);
              return;
            }
            if (projectTreeUi.expandedProjectIds.has(projectId)) {
              projectTreeUi.expandedProjectIds.delete(projectId);
            } else {
              rememberExpandedProject(projectId);
            }
            renderThreadList();
          });
          branch.appendChild(toggle);

          const threadGroup = document.createElement("div");
          threadGroup.className = "project-branch__threads";
          threadGroup.id = branchDomId;
          threadGroup.hidden = !isExpanded;
          threadGroup.setAttribute("role", "group");

          if (isExpanded) {
            if (!cachedThreads.length) {
              const empty = document.createElement("p");
              empty.className = "thread-tree__empty";
              empty.textContent = isActiveProject ? "目前尚無對話串。" : "切換此專案後顯示對話串。";
              threadGroup.appendChild(empty);
            } else {
              const activeThreadId = String(state.activeThreadId || "").trim();
              cachedThreads.forEach((thread) => {
                const threadId = String(thread.thread_id || "").trim();
                if (!threadId) return;
                const row = document.createElement("button");
                row.type = "button";
                row.className = "thread-row";
                row.dataset.threadId = threadId;
                const isActiveThread = isActiveProject && threadId === activeThreadId;
                row.classList.toggle("is-active", isActiveThread);
                row.innerHTML = `
                  <strong class="thread-row__title">${escapeHtml(String(thread.title || threadId))}</strong>
                  <span class="thread-row__meta">${isActiveThread ? "目前對話 · " : ""}${escapeHtml(formatThreadUpdatedAt(thread.updated_at))}</span>
                `;
                row.addEventListener("click", () => void selectActiveThread(threadId));
                threadGroup.appendChild(row);
              });
            }
          }

          branch.appendChild(threadGroup);
          fragment.appendChild(branch);
        });
        elements.threadList.innerHTML = "";
        elements.threadList.appendChild(fragment);
      }

      function renderRollupPreview() {
        const activeThreadId = String(state.activeThreadId || "").trim();
        if (!activeThreadId) return;
        const targetThread = (state.threadList || []).find((item) => String(item.thread_id || "").trim() === activeThreadId);
        if (!targetThread) return;
        appendTimelineStatus(`已載入 Thread 摘要：${targetThread.title || activeThreadId}（更新：${formatThreadUpdatedAt(targetThread.updated_at)}）`);
      }

      async function loadProjects() {
        let projects = [];
        try {
          projects = await services.runs.listProjects();
        } catch (error) {
          throw error;
        }
        projects = projects.map(normalizeProjectRecord).filter(Boolean);
        const availableIds = new Set(projects.map((project) => project.project_id));
        if (state.projectId && !availableIds.has(state.projectId)) {
          state.projectId = null;
        }
        appStore.patch({
          layout: {
            ...(appStore.getState().layout || {}),
            projects,
            projectId: state.projectId,
          },
        });
        renderProjectSelectOptions(projects);
        syncContextHeader();
        renderThreadList();
        if (!projects.length) {
          showToast("尚無專案，請在聊天輸入：建立專案 <名稱>");
        }
        elements.refreshContext.disabled = !state.projectId;
      }

      async function ensureActiveThread(token = state.pendingProjectLoadToken) {
        if (!state.projectId || !isCurrentProjectHydrationToken(token)) return;
        const existingThreadId = String(state.activeThreadId || "").trim();
        if (existingThreadId) {
          return;
        }
        const payload = await services.threads.createProjectThread(state.projectId);
        if (!isCurrentProjectHydrationToken(token)) return;
        state.activeThreadId = payload.active_thread_id || payload.thread_id || null;
        if (state.activeThreadId) {
          state.activeThreadByProject[state.projectId] = state.activeThreadId;
        }
        await loadThreadList(token);
      }

      async function loadThreadList(token = state.pendingProjectLoadToken) {
        if (!state.projectId || !isCurrentProjectHydrationToken(token)) {
          state.threadList = [];
          renderThreadList();
          return;
        }
        const payload = await services.threads.listProjectThreads(state.projectId);
        if (!isCurrentProjectHydrationToken(token)) return;
        const threads = (Array.isArray(payload.threads) ? payload.threads : []).map(normalizeThreadRecord).filter(Boolean);
        const activeThreadId = String(payload.active_thread_id || "").trim() || null;
        const cachedActiveThreadId = String(state.activeThreadByProject[state.projectId] || "").trim() || null;
        state.threadList = threads;
        state.threadsByProject[state.projectId] = threads;
        state.activeThreadId = activeThreadId || cachedActiveThreadId || state.activeThreadId || null;
        if (state.activeThreadId) {
          state.activeThreadByProject[state.projectId] = state.activeThreadId;
        }
        state.threadList = state.threadList.map((thread) => ({
          ...thread,
          is_active: String(thread.thread_id || "").trim() === String(state.activeThreadId || "").trim(),
        }));
        renderThreadList();
      }

      async function selectActiveThread(threadId, token = state.pendingProjectLoadToken) {
        if (!state.projectId) return;
        const normalizedThreadId = String(threadId || "").trim();
        if (!normalizedThreadId) return;
        await services.threads.setActiveThread(state.projectId, normalizedThreadId);
        if (!isCurrentProjectHydrationToken(token)) return;
        state.activeThreadId = normalizedThreadId;
        state.activeThreadByProject[state.projectId] = normalizedThreadId;
        state.threadList = (state.threadList || []).map((thread) => ({
          ...thread,
          is_active: String(thread.thread_id || "").trim() === normalizedThreadId,
        }));
        renderThreadList();
        await loadProjectHistory(token);
        await loadContext(token);
      }

      async function createThreadAndActivate(token = state.pendingProjectLoadToken) {
        if (!state.projectId) {
          showToast("請先選擇專案。", 9000, "warning");
          return;
        }
        const payload = await services.threads.createProjectThread(state.projectId);
        if (!isCurrentProjectHydrationToken(token)) return;
        state.activeThreadId = payload.active_thread_id || payload.thread_id || null;
        if (state.activeThreadId) {
          state.activeThreadByProject[state.projectId] = state.activeThreadId;
        }
        await loadThreadList(token);
        await loadProjectHistory(token);
        await loadContext(token);
      }

      async function loadContext(token = state.pendingProjectLoadToken) {
        if (!state.projectId) {
          showToast("請先選擇專案。");
          return;
        }
        let payload;
        try {
          payload = await services.threads.getProjectThreadContext(state.projectId, state.activeThreadId || "");
        } catch (error) {
          if (isMissingProjectError(error)) {
            await recoverFromMissingProject(error, { source: "load_context" });
            return;
          }
          throw error;
        }
        if (!isCurrentProjectHydrationToken(token)) return;
        state.graph = payload.graph || { nodes: [], edges: [] };
        state.graphRunId = payload.run_id || null;
        state.graphNodeStates = payload.node_states || {};
        state.graphEvents = payload.recent_events || [];
        const runtimeVm = buildGraphRuntimeViewModel({ graphPayload: payload });
        if (runtimeVm.diagnostics.length) {
          logUiDebug("context.graph-runtime", {
            run_id: runtimeVm.runId,
            diagnostics: runtimeVm.diagnostics,
            node_count: runtimeVm.nodes.length,
          });
        }
        elements.graphCode.textContent = payload.graph_mermaid || "";
        renderGraph(payload.graph_mermaid || "");
        renderNodeList();
        renderRunMeta(state.graphRunId, payload.run_status);
        renderDocs(payload.docs || []);
        const docCount = (payload.docs || []).length;
        const hasGraph = payload.graph_mermaid ? "有" : "無";
        const runHint = state.graphRunId ? `已連結 Run ${shortenId(state.graphRunId)}` : "尚未有 Run";
        elements.contextOverview.textContent = `已同步專案內容：Graph ${hasGraph}、文件 ${docCount} 筆；${runHint}。`;
        elements.contextOverview.title = state.graphRunId ? `完整 Run ID：${state.graphRunId}` : "尚未取得任何 Run。";
        const statusSet = new Set(runtimeVm.nodes.map((node) => node.effectiveStatus));
        const hasFailedNode = statusSet.has("failed");
        const hasRunningNode = statusSet.has("running");
        const hasUnknownNode = statusSet.has("unknown");
        updateExecutionStep("node_status", {
          title: "Node 狀態",
          status: hasFailedNode ? "failed" : hasRunningNode ? "running" : hasUnknownNode ? "pending" : runtimeVm.nodes.length ? "succeeded" : "pending",
          details: runtimeVm.nodes.length ? `共 ${runtimeVm.nodes.length} 個節點狀態已同步` : "尚無節點事件",
          inferred: false,
        });
        await loadRunArtifacts();
      }

      function normalizeDocItem(doc) {
        if (typeof doc === "string") {
          return {
            path: doc,
            name: doc.split("/").pop() || doc,
            run_id: "尚未取得 Run ID",
            node_id: "尚未取得 Node ID",
            task_id: "未分組 Task",
            open_url: null,
            download_url: null,
          };
        }
        return {
          path: doc.path || "",
          name: doc.name || (doc.path || "").split("/").pop() || "(未命名)",
          run_id: doc.run_id || "尚未取得 Run ID",
          node_id: doc.node_id || "尚未取得 Node ID",
          task_id: doc.task_id || "未分組 Task",
          open_url: doc.open_url || null,
          download_url: doc.download_url || null,
        };
      }

      function renderDocs(docs) {
        const normalized = (docs || []).map(normalizeDocItem);
        state.docsItems = normalized;
        state.docsFilteredItems = normalized.filter((doc) => {
          const query = state.docsFilterQuery.trim().toLowerCase();
          if (!query) return true;
          return doc.path.toLowerCase().includes(query) || doc.name.toLowerCase().includes(query);
        });
        if (!state.docsFilteredItems.length) {
          state.docsSelectedPath = null;
          elements.docsOpen.disabled = true;
          elements.docsDownload.disabled = true;
          elements.docsInsert.disabled = true;
          elements.docsPreviewTitle.textContent = "尚無文件";
          elements.docsPreviewMeta.textContent = "可將檔案放入專案 docs/ 目錄（支援 .md/.txt/.json/.py/.js 等）";
          elements.docsPreviewContent.innerHTML = '<p class="empty-context">目前沒有可預覽文件。請把文件放到 <code>docs/</code> 後重新整理。</p>';
          return;
        }
        state.docsFlatItems = buildDocsTree(state.docsFilteredItems);
      }

      function buildDocsTree(items = []) {
        const grouped = new Map();
        items.forEach((doc) => {
          const runKey = `run:${doc.run_id || "尚未取得 Run ID"}`;
          if (!grouped.has(runKey)) {
            grouped.set(runKey, { type: "group", key: runKey, label: `Run ${doc.run_id || "尚未取得 Run ID"}` });
          }
          const taskKey = `${runKey}/task:${doc.task_id || "ungrouped"}`;
          if (!grouped.has(taskKey)) {
            grouped.set(taskKey, { type: "group", key: taskKey, label: `Task ${doc.task_id || "未分組 Task"}`, depth: 1 });
          }
        });

        const flat = [];
        Array.from(grouped.values()).forEach((entry) => {
          if (entry.depth !== 1) {
            flat.push({ ...entry, depth: 0 });
            Array.from(grouped.values())
              .filter((task) => task.depth === 1 && task.key.startsWith(entry.key))
              .forEach((task) => {
                flat.push(task);
                items
                  .filter((doc) => task.key === `run:${doc.run_id || "尚未取得 Run ID"}/task:${doc.task_id || "未分組 Task"}`)
                  .forEach((doc) => {
                    flat.push({ type: "doc", depth: 2, key: doc.path, doc });
                  });
              });
          }
        });
        return flat;
      }

      function renderDocsVirtualList() {
        const viewport = elements.docsTreeViewport;
        const total = state.docsFlatItems.length;
        if (!total) {
          viewport.innerHTML = '<p class="empty-context">尚無文件可顯示。請將文件放到專案 <code>docs/</code> 目錄後重新整理。</p>';
          return;
        }
        const rowHeight = state.docsVirtual.rowHeight;
        const scrollTop = viewport.scrollTop;
        const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - state.docsVirtual.buffer);
        const visibleCount = Math.ceil(viewport.clientHeight / rowHeight) + state.docsVirtual.buffer * 2;
        const endIndex = Math.min(total, startIndex + visibleCount);

        const spacerTop = startIndex * rowHeight;
        const spacerBottom = Math.max(0, (total - endIndex) * rowHeight);

        const fragment = document.createDocumentFragment();
        if (spacerTop > 0) {
          const top = document.createElement("div");
          top.style.height = `${spacerTop}px`;
          fragment.appendChild(top);
        }

        state.docsFlatItems.slice(startIndex, endIndex).forEach((item) => {
          const row = document.createElement("button");
          row.type = "button";
          row.className = `docs-row docs-row--${item.type}`;
          row.style.paddingLeft = `${12 + item.depth * 16}px`;
          row.setAttribute("role", "listitem");
          if (item.type === "doc") {
            row.textContent = `${item.doc.name} · ${item.doc.node_id}`;
            row.classList.toggle("is-active", state.docsSelectedPath === item.doc.path);
            row.addEventListener("click", () => selectDoc(item.doc.path));
          } else {
            row.disabled = true;
            row.textContent = item.label;
          }
          fragment.appendChild(row);
        });

        if (spacerBottom > 0) {
          const bottom = document.createElement("div");
          bottom.style.height = `${spacerBottom}px`;
          fragment.appendChild(bottom);
        }

        viewport.replaceChildren(fragment);
      }

      function getSelectedDoc() {
        return state.docsItems.find((item) => item.path === state.docsSelectedPath) || null;
      }

      async function selectDoc(docPath) {
        state.docsSelectedPath = docPath;
        renderDocsVirtualList();
        const selected = getSelectedDoc();
        if (!selected) return;
        elements.docsPreviewTitle.textContent = selected.path;
        elements.docsPreviewMeta.textContent = `run_id：${selected.run_id}｜node_id：${selected.node_id}`;
        elements.docsOpen.disabled = false;
        elements.docsDownload.disabled = false;
        elements.docsInsert.disabled = false;
        try {
          const payload = await services.docs.getDoc(state.projectId, selected.path);
          const lowerPath = selected.path.toLowerCase();
          if (/\.(md|markdown)$/i.test(lowerPath)) {
            elements.docsPreviewContent.innerHTML = renderMarkdown(payload.content || "");
          } else {
            elements.docsPreviewContent.innerHTML = `<pre><code>${escapeHtml(payload.content || "")}</code></pre>`;
          }
          highlightPreviewBlocks(elements.docsPreviewContent);
        } catch (error) {
          elements.docsPreviewContent.innerHTML = `<p class="empty-context">預覽失敗：${escapeHtml(error.message)}</p>`;
        }
      }

      async function loadDocsPage() {
        if (!state.projectId) {
          elements.docsTreeMeta.textContent = "請先選擇專案。";
          state.docsSelectedPath = null;
          elements.docsOpen.disabled = true;
          elements.docsDownload.disabled = true;
          elements.docsInsert.disabled = true;
          elements.docsPreviewTitle.textContent = "請從左側選擇文件";
          elements.docsPreviewMeta.textContent = "來源 run / node 將顯示於此。";
          elements.docsPreviewContent.innerHTML = '<p class="empty-context">尚未選擇文件。</p>';
          state.docsFlatItems = [];
          renderDocsVirtualList();
          return;
        }
        const docs = (await services.docs.listDocs(state.projectId)).map(normalizeDocItem);
        renderDocs(docs);
        elements.docsTreeMeta.textContent = `共 ${state.docsFilteredItems.length} / ${docs.length} 份文件（虛擬列表）`;
        if (!state.docsFilteredItems.find((doc) => doc.path === state.docsSelectedPath)) {
          state.docsSelectedPath = state.docsFilteredItems[0]?.path || null;
        }
        renderDocsVirtualList();
        if (state.docsSelectedPath) {
          await selectDoc(state.docsSelectedPath);
        }
      }

      async function renderGraph(code) {
        elements.graphPreview.innerHTML = "";
        if (state.graphPanZoom) {
          state.graphPanZoom.destroy();
          state.graphPanZoom = null;
        }
        const nodeCount = Array.isArray(state.graph?.nodes) ? state.graph.nodes.length : 0;
        const edgeCount = Array.isArray(state.graph?.edges) ? state.graph.edges.length : 0;
        if (!code && nodeCount === 0) return;
        elements.graphPreview.innerHTML = `<p class="graph-empty-state">Graph 已同步：${nodeCount} 個節點、${edgeCount} 條連線。請切到「流程圖」頁查看互動式視圖。</p>`;
      }

      function buildCurrentRuntimeViewModel() {
        return buildGraphRuntimeViewModel({
          graphPayload: {
            graph: state.graph,
            graph_mermaid: elements.graphCode?.textContent || "",
            node_states: state.graphNodeStates,
            run_id: state.graphRunId,
          },
          runMeta: { run_id: state.graphRunId },
        });
      }

      function renderNodeList() {
        elements.graphNodeList.innerHTML = "";
        const runtimeVm = buildCurrentRuntimeViewModel();
        if (runtimeVm.diagnostics.length) {
          logUiDebug("graph.node-list", { diagnostics: runtimeVm.diagnostics, run_id: runtimeVm.runId });
        }
        const nodes = runtimeVm.nodes || [];
        if (!nodes.length) return;
        nodes.forEach((nodeVm) => {
          const item = document.createElement("li");
          item.className = "graph-node-item";
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "graph-node-item__button";
          btn.innerHTML = `<span>${nodeVm.id}</span><span class="node-status ${nodeVm.statusUi.cssClass}">${nodeVm.statusUi.label}</span>`;
          btn.addEventListener("click", () => openNodeDrawer(nodeVm.id));
          item.appendChild(btn);
          elements.graphNodeList.appendChild(item);
        });
      }

      function decorateMermaidNodes() {
        const runtimeVm = buildCurrentRuntimeViewModel();
        const statusById = new Map(runtimeVm.nodes.map((node) => [node.id, node]));
        const groups = elements.graphPreview.querySelectorAll("g.node");
        groups.forEach((group) => {
          const label = group.querySelector(".nodeLabel")?.textContent?.trim();
          if (!label) return;
          const nodeVm = statusById.get(label);
          group.classList.add(nodeVm?.statusUi?.mermaidClass || "node-status--unknown");
          group.style.cursor = "pointer";
          group.setAttribute("role", "button");
          group.setAttribute("tabindex", "0");
          group.setAttribute("aria-label", `開啟 ${label} 節點詳細資訊`);
          group.addEventListener("click", () => openNodeDrawer(label));
          group.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            openNodeDrawer(label);
          });
        });
      }

      function inferNodeInputs(node) {
        const payload = {};
        ["args", "input", "inputs", "prompt", "content", "tool"].forEach((key) => {
          if (node[key] !== undefined) payload[key] = node[key];
        });
        return payload;
      }

      function extractOutputArtifacts(output) {
        if (!output || typeof output !== "object") return { docs: [], artifacts: [], raw: output };
        return {
          docs: output.docs || output.documents || [],
          artifacts: output.artifacts || output.files || [],
          raw: output,
        };
      }

      function openNodeDrawer(nodeId) {
        const node = (state.graph?.nodes || []).find((item) => item.id === nodeId);
        if (!node) return;
        state.graphSelectedNodeId = nodeId;
        const runtimeVm = buildCurrentRuntimeViewModel();
        const nodeVm = runtimeVm.nodes.find((item) => item.id === nodeId);
        const nodeState = nodeVm?.runtimeState || {};
        const executionEngine = node.type && String(node.type).includes("tool") ? "tool" : "llm";
        elements.graphNodeTitle.textContent = `Node：${nodeId}`;
        elements.graphNodeMeta.textContent = `status：${nodeVm?.statusUi?.label || "未知"} ｜ execution_engine：${executionEngine}`;
        elements.graphNodeInputs.textContent = JSON.stringify(inferNodeInputs(node), null, 2);
        elements.graphNodeOutputs.textContent = JSON.stringify(extractOutputArtifacts(nodeState.output), null, 2);
        elements.graphNodeEvents.innerHTML = "";
        state.graphEvents
          .filter((event) => event.node_id === nodeId || event.from === nodeId || event.to === nodeId)
          .slice(-8)
          .forEach((event) => {
            const item = document.createElement("li");
            item.textContent = JSON.stringify(event);
            elements.graphNodeEvents.appendChild(item);
          });
        if (!elements.graphNodeEvents.children.length) {
          const item = document.createElement("li");
          item.textContent = "尚無 events/logs";
          elements.graphNodeEvents.appendChild(item);
        }
        elements.graphNodeDrawer.hidden = false;
      }

      function closeNodeDrawer() {
        elements.graphNodeDrawer.hidden = true;
      }

      function queuePlanCommand(command, args, description) {
        showPlanCard({
          command,
          args,
          plan_card: `${description}\n\ncommand: ${command}\nargs: ${JSON.stringify(args, null, 2)}`,
        });
      }

      function showPlanCard(plan) {
        state.plan = plan;
        elements.planContent.textContent = plan.plan_card || "";
        renderPlanList(elements.planCommands, plan.commands || []);
        renderPlanList(elements.planPatches, plan.graph_patches || []);
        renderPlanRisk(plan);
        elements.planCard.hidden = false;
      }

      async function applySessionFromEvent(data) {
        if (!data) return;
        let projectChanged = false;
        const eventProjectId = normalizeProjectIdForUi(data.project_id);
        const eventThreadId = String(data.thread_id || "").trim();
        const activeProjectId = normalizeProjectIdForUi(state.projectId);
        const handoff = data.thread_handoff && typeof data.thread_handoff === "object" ? data.thread_handoff : null;
        const handoffSourceProjectId = normalizeProjectIdForUi(handoff?.source_project_id);
        const handoffTargetProjectId = normalizeProjectIdForUi(handoff?.target_project_id);
        const shouldForceSwitchProject = Boolean(
          handoff &&
          eventProjectId &&
          handoffTargetProjectId === eventProjectId &&
          (!activeProjectId || activeProjectId === handoffSourceProjectId || activeProjectId === eventProjectId)
        );

        if (shouldForceSwitchProject) {
          setProjectState(eventProjectId);
          projectChanged = true;
        } else if (eventProjectId && !activeProjectId) {
          // 僅在「無專案模式」下，才讓事件自動切換專案，避免切換專案後被舊串流事件覆寫。
          setProjectState(eventProjectId);
          projectChanged = true;
        }

        const latestActiveProjectId = normalizeProjectIdForUi(state.projectId);
        const shouldApplyToActiveProject = shouldForceSwitchProject || !eventProjectId || eventProjectId === latestActiveProjectId;
        if (shouldApplyToActiveProject && eventThreadId) {
          state.activeThreadId = eventThreadId;
        }
        if (shouldApplyToActiveProject && Array.isArray(data.artifacts)) {
          state.runArtifacts = data.artifacts.filter((artifact) => !isConversationArtifact(artifact));
          renderArtifactsInspector(state.runArtifacts);
        }
        if (projectChanged) {
          await loadProjects();
        }
      }

      async function confirmPlan(confirmed) {
        if (!state.plan) return;
        try {
          const path = state.plan.confirm_api || "/threads/plan/confirm";
          const payload =
            path === "/threads/plan/confirm"
              ? await services.admin.confirmPlan(path, {
                  project_id: state.projectId,
                  thread_id: state.activeThreadId,
                  command: state.plan.command,
                  args: state.plan.args || {},
                  confirmed,
                })
              : await services.admin.confirmPlan(path, { ...state.plan.args, confirmed });
          appendMessage("agent", confirmed ? "已確認執行。" : "已取消執行。");
          if (confirmed && state.plan?.command === "graph.template.create") {
            state.graphTemplateId = payload.result?.template_id || state.graphTemplateId;
            if (state.graphTemplateId) {
              showToast(`Template 已建立：${state.graphTemplateId}`);
            }
          }
          resetPlanCard();
          if (state.projectId) {
            await loadContext();
          }
          if (path !== "/threads/plan/confirm") {
            await loadToolsSkillsPage();
          }
        } catch (error) {
          showToast(`Plan 執行失敗：${error.message}`);
        }
      }

      function buildAttachmentSummary(attachments) {
        if (!attachments || attachments.length === 0) return "";
        const lines = attachments.map((file) => {
          const sizeKb = Math.round(file.size / 1024);
          return `- ${file.name} (${file.type || "未知格式"}, ${sizeKb} KB)`;
        });
        return `\n\n[附件摘要]\n${lines.join("\n")}`;
      }

      function updateThinking(payload = {}) {
        const mode = state.thinkingMode;
        if (mode === "off") {
          elements.thinkingSummary.textContent = "Thinking 顯示已關閉";
          elements.thinkingDetail.textContent = "";
          return;
        }
        const status = payload.status || "分析中";
        const brief = payload.brief || "正在整理回覆與執行計畫";
        elements.thinkingSummary.textContent = `狀態：${status}｜${brief}`;
        elements.thinkingDetail.textContent = mode === "verbose" ? (payload.verbose || brief) : brief;
      }

      function formatFileSize(bytes) {
        const size = Number(bytes || 0);
        if (!Number.isFinite(size) || size <= 0) return "0 B";
        const units = ["B", "KB", "MB", "GB"];
        let value = size;
        let idx = 0;
        while (value >= 1024 && idx < units.length - 1) {
          value /= 1024;
          idx += 1;
        }
        return `${value.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
      }

      function isImageMime(mime = "") {
        return String(mime).startsWith("image/");
      }

      function isTextLikeMime(mime = "") {
        const target = String(mime).toLowerCase();
        return target.startsWith("text/") || ["application/json", "application/xml", "application/javascript"].includes(target);
      }

      function isMarkdownPath(name = "") {
        return /\.(md|markdown)$/i.test(name);
      }

      function isWorkspaceHtmlArtifact(artifact = {}) {
        const path = String(artifact.path || "").toLowerCase();
        return path.startsWith("workspace/") && path.endsWith(".html");
      }

      function pickArtifactsEntrypoint(artifacts = []) {
        const exact = artifacts.find((artifact) => String(artifact.path || "").toLowerCase() === "workspace/index.html");
        if (exact) return exact;
        return artifacts.find((artifact) => isWorkspaceHtmlArtifact(artifact)) || null;
      }

      function withPreviewRefreshToken(url = "") {
        if (!url) return "";
        const separator = url.includes("?") ? "&" : "?";
        return `${url}${separator}_preview_ts=${Date.now()}`;
      }

      function isConversationArtifact(artifact = {}) {
        const path = String(artifact.path || "").toLowerCase();
        const name = String(artifact.name || "").toLowerCase();
        const runId = String(state.graphRunId || "").toLowerCase();
        if (!runId) return false;
        return path.startsWith(`docs/single_${runId}`) || name.startsWith(`single_${runId}`);
      }

      async function loadRunArtifacts() {
        if (!state.projectId || !state.graphRunId) {
          state.runArtifacts = [];
          renderArtifactsInspector([]);
          return;
        }
        try {
          const artifacts = await services.artifacts.listArtifacts(state.graphRunId, state.projectId);
          state.runArtifacts = artifacts.filter((artifact) => !isConversationArtifact(artifact));
          renderArtifactsInspector(state.runArtifacts);
        } catch (error) {
          if (isMissingProjectError(error)) {
            await recoverFromMissingProject(error, { source: "load_run_artifacts", run_id: state.graphRunId || null });
            return;
          }
          state.runArtifacts = [];
          renderArtifactsInspector([]);
          showToast(`載入 artifacts 失敗：${error.message}`, 9000, "danger");
        }
      }

      const INLINE_PREVIEW_SANDBOX = "allow-scripts allow-forms allow-modals";

      function ensureInlinePreviewSandbox() {
        if (!elements.artifactsInlinePreviewFrame) return;
        elements.artifactsInlinePreviewFrame.setAttribute("sandbox", INLINE_PREVIEW_SANDBOX);
      }

      function renderArtifactsInspector(artifacts = []) {
        elements.artifactsInspectorList.innerHTML = "";
        const entrypoint = pickArtifactsEntrypoint(artifacts);
        const compactItems = entrypoint ? artifacts.filter((artifact) => artifact !== entrypoint) : artifacts;

        if (!state.graphRunId) {
          elements.artifactsOverview.textContent = "尚未偵測到 Run，請先執行流程。";
          elements.artifactsEmpty.hidden = false;
          elements.artifactsInlinePreview.hidden = true;
          elements.artifactsListDetails.open = false;
          return;
        }
        elements.artifactsOverview.textContent = `Run ${shortenId(state.graphRunId)} 共 ${artifacts.length} 份產出物。`;
        if (!artifacts.length) {
          elements.artifactsEmpty.hidden = false;
          elements.artifactsInlinePreview.hidden = true;
          elements.artifactsListDetails.open = false;
          return;
        }
        elements.artifactsEmpty.hidden = true;

        if (entrypoint) {
          elements.artifactsInlinePreview.hidden = false;
          elements.artifactsInlinePreviewTitle.textContent = entrypoint.path || entrypoint.name || "workspace/index.html";
          ensureInlinePreviewSandbox();
          elements.artifactsInlinePreviewFrame.src = withPreviewRefreshToken(entrypoint.url || "");
          elements.artifactsPreviewOpenTab.onclick = () => window.open(entrypoint.url, "_blank", "noopener");
          elements.artifactsPreviewRefresh.onclick = () => {
            ensureInlinePreviewSandbox();
            elements.artifactsInlinePreviewFrame.src = withPreviewRefreshToken(entrypoint.url || "");
          };
        } else {
          elements.artifactsInlinePreview.hidden = true;
          elements.artifactsInlinePreviewFrame.removeAttribute("src");
          elements.artifactsPreviewOpenTab.onclick = null;
          elements.artifactsPreviewRefresh.onclick = null;
        }

        elements.artifactsListDetails.open = false;
        if (!compactItems.length) {
          elements.artifactsListDetails.hidden = true;
          return;
        }
        elements.artifactsListDetails.hidden = false;

        compactItems.forEach((artifact) => {
          const card = document.createElement("article");
          card.className = "artifact-inspector-card";

          const header = document.createElement("header");
          const title = document.createElement("strong");
          title.textContent = artifact.name || artifact.path || "(未命名)";
          const meta = document.createElement("span");
          const parts = [formatFileSize(artifact.size)];
          if (artifact.createdAt || artifact.created_at) parts.push(artifact.createdAt || artifact.created_at);
          meta.textContent = parts.join(" · ");
          header.append(title, meta);
          card.appendChild(header);

          const path = document.createElement("p");
          path.className = "artifact-inspector-card__path";
          path.textContent = artifact.path || "";
          card.appendChild(path);

          const actions = document.createElement("div");
          actions.className = "artifact-inspector-card__actions";
          const openBtn = document.createElement("button");
          openBtn.type = "button";
          openBtn.className = "secondary-btn small";
          openBtn.textContent = "開啟";
          openBtn.addEventListener("click", () => window.open(artifact.url || artifact.download_url, "_blank", "noopener"));
          const downloadBtn = document.createElement("button");
          downloadBtn.type = "button";
          downloadBtn.className = "secondary-btn small";
          downloadBtn.textContent = "下載";
          downloadBtn.addEventListener("click", () => window.open(artifact.download_url || artifact.url, "_blank", "noopener"));
          actions.append(openBtn, downloadBtn);
          card.appendChild(actions);

          elements.artifactsInspectorList.appendChild(card);
        });
      }

      async function openArtifactPreview(artifact) {
        if (!artifact) return;
        state.artifactPreviewItem = artifact;
        elements.artifactPreviewTitle.textContent = artifact.name || artifact.path || "Artifact 預覽";
        elements.artifactPreviewBody.innerHTML = "";
        elements.artifactPreviewCopy.hidden = true;
        elements.artifactPreviewDownload.onclick = () => window.open(artifact.download_url, "_blank", "noopener");

        const mime = String(artifact.mime || "").toLowerCase();
        if (isImageMime(mime)) {
          const img = document.createElement("img");
          img.src = artifact.url;
          img.alt = artifact.name || "artifact";
          img.className = "artifact-preview-content-image";
          elements.artifactPreviewBody.appendChild(img);
        } else if (mime === "application/pdf") {
          const frame = document.createElement("iframe");
          frame.src = artifact.url;
          frame.className = "artifact-preview-content-frame";
          frame.title = artifact.name || "PDF 預覽";
          elements.artifactPreviewBody.appendChild(frame);
        } else if (isTextLikeMime(mime) || isMarkdownPath(artifact.name || artifact.path || "")) {
          try {
            const response = await fetch(artifact.url);
            if (!response.ok) throw new Error("讀取失敗");
            const text = await response.text();
            const wrapper = document.createElement("div");
            if (isMarkdownPath(artifact.name || artifact.path || "")) {
              const html = renderMarkdown(text);
              wrapper.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
            } else {
              const pre = document.createElement("pre");
              pre.textContent = text;
              wrapper.appendChild(pre);
            }
            elements.artifactPreviewBody.appendChild(wrapper);
            elements.artifactPreviewCopy.hidden = false;
            elements.artifactPreviewCopy.onclick = async () => {
              await copyText(text, {
                toast: (message, options = {}) => showToast(message, options.duration || 6000, options.type || "success"),
              });
            };
          } catch (error) {
            const fallback = document.createElement("p");
            fallback.className = "empty-context";
            fallback.textContent = `預覽失敗，請改用下載：${error.message}`;
            elements.artifactPreviewBody.appendChild(fallback);
          }
        } else {
          const fallback = document.createElement("p");
          fallback.className = "empty-context";
          fallback.textContent = "此檔案類型暫不支援內嵌預覽，請使用下載。";
          elements.artifactPreviewBody.appendChild(fallback);
        }

        elements.artifactPreviewModal.hidden = false;
        elements.artifactPreviewModal.setAttribute("aria-hidden", "false");
      }

      function closeArtifactPreview() {
        elements.artifactPreviewModal.hidden = true;
        elements.artifactPreviewModal.setAttribute("aria-hidden", "true");
        elements.artifactPreviewBody.innerHTML = "";
        state.artifactPreviewItem = null;
      }

      function appendArtifactsHintToTimeline(count = 0) {
        if (!state.graphRunId) return;
        const row = document.createElement("article");
        row.className = "timeline-status timeline-status--artifacts";
        const hint = document.createElement("button");
        hint.type = "button";
        hint.className = "secondary-btn small";
        hint.textContent = `Artifacts 產出：${count} 份（點我查看）`;
        hint.addEventListener("click", () => focusInspectorSection("artifacts"));
        row.appendChild(hint);
        elements.timeline.appendChild(row);
      }

      function renderArtifacts(artifacts = []) {
        if (!elements.artifactList) {
          return;
        }
        elements.artifactList.innerHTML = "";
        if (!artifacts.length) {
          elements.artifactList.innerHTML = '<p class="empty-context">目前尚無 artifact</p>';
          return;
        }
        artifacts.forEach((artifact) => {
          const card = document.createElement("article");
          card.className = "artifact-card";
          card.innerHTML = `
            <header>
              <strong>${artifact.type}</strong>
              <span>${artifact.run_id}/${artifact.node_id}</span>
            </header>
            <p>${artifact.path}</p>
            <pre>${escapeHtml(artifact.preview || "(無預覽)")}</pre>`;
          elements.artifactList.appendChild(card);
        });
      }

      elements.shellNavItems.forEach((link) => {
        link.addEventListener("click", (event) => {
          event.preventDefault();
          const routeKey = link.dataset.route || "chat";
          navigateToRoute(routeKey);
        });
      });

      window.addEventListener("hashchange", () => {
        const routeKey = resolveRouteFromHash();
        void applyRoute(routeKey);
      });


      elements.toolsSkillsSearch?.addEventListener("input", (event) => {
        toolsSkillsUi.search = event.target.value || "";
        renderToolsSkillsPage();
      });
      elements.toolsSkillsTabList?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-target-panel]");
        if (!button) return;
        const nextTab = button.id === "tools-skills-tab-skills" ? "skills" : "tools";
        setToolsSkillsTab(nextTab);
      });
      elements.toolsSkillsTabList?.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
          return;
        }
        event.preventDefault();
        const currentIndex = TAB_SEQUENCE.indexOf(toolsSkillsUi.activeTab);
        let nextIndex = currentIndex;
        if (event.key === "Home") nextIndex = 0;
        if (event.key === "End") nextIndex = TAB_SEQUENCE.length - 1;
        if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + TAB_SEQUENCE.length) % TAB_SEQUENCE.length;
        if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % TAB_SEQUENCE.length;
        setToolsSkillsTab(TAB_SEQUENCE[nextIndex], { focus: true });
      });
      elements.toolsFilterChips?.addEventListener("click", (event) => {
        const chip = event.target.closest("[data-tools-filter]");
        if (!chip) return;
        toolsSkillsUi.toolsFilter = chip.dataset.toolsFilter || "all";
        renderToolsSkillsPage();
      });
      elements.skillsSourceFilters?.addEventListener("click", (event) => {
        const chip = event.target.closest("[data-skills-source]");
        if (!chip) return;
        toolsSkillsUi.skillsSource = chip.dataset.skillsSource || "all";
        renderToolsSkillsPage();
      });
      elements.skillsViewToggle?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-skills-view]");
        if (!button) return;
        toolsSkillsUi.skillsView = button.dataset.skillsView === "list" ? "list" : "grid";
        renderToolsSkillsPage();
      });
      elements.toolsList?.addEventListener("click", (event) => {
        const button = event.target.closest("[data-tool-action]");
        if (!button) return;
        const toolName = button.dataset.toolName || "";
        const enabled = button.dataset.toolEnabled === "true";
        const requireConfirm = button.dataset.toolRequireConfirm === "true";
        if (!toolName) return;
        if (button.dataset.toolAction === "toggle-enabled") {
          queueToolPolicyPlan(toolName, enabled ? "disable" : "enable", requireConfirm);
          return;
        }
        if (button.dataset.toolAction === "toggle-confirm") {
          queueToolPolicyPlan(toolName, "require_confirm", !requireConfirm);
        }
      });
      elements.toolsSkillsRefresh.addEventListener("click", loadToolsSkillsPage);
      elements.configRefresh.addEventListener("click", loadConfigPage);
      elements.configSearch.addEventListener("input", renderConfigTable);
      elements.configExport.addEventListener("click", exportEffectiveConfig);
      elements.configEditApply?.addEventListener("click", () => {
        void applyConfigUpdate();
      });
      elements.plannerToggleBtn?.addEventListener("click", () => {
        void togglePlannerEnabled();
      });
      elements.configWebSearchApply?.addEventListener("click", () => {
        void applyWebSearchConfig();
      });
      elements.skillTriggerPreview.addEventListener("click", async () => {
        const skillName = elements.skillTriggerSelect.value;
        if (!skillName) {
          showToast("請先選擇 skill。");
          return;
        }
        try {
          const payload = await services.admin.getSkillTriggerPreview(skillName, state.projectId || "");
          elements.skillInjectionPreview.textContent = JSON.stringify(payload, null, 2);
          elements.skillsPreviewMeta.textContent = `最近預覽：${skillName}`;
          showToast("已產生 skill 注入預覽。");
        } catch (error) {
          showToast(`技能預覽失敗：${error.message}`);
        }
      });
      elements.skillTriggerSelect?.addEventListener("change", updateSkillsPreviewMeta);

      elements.logsTabLogs?.addEventListener("click", () => setLogsEventsPanel("logs"));
      elements.logsTabEvents?.addEventListener("click", () => setLogsEventsPanel("events"));

      elements.logsSeverityChips?.addEventListener("click", (event) => {
        const chip = event.target.closest(".chip[data-severity]");
        if (!chip) return;
        const severity = String(chip.dataset.severity || "");
        elements.logsFilterSeverity.value = severity;
        setSeverityChipActive(severity);
        void loadLogsPage(1);
      });

      elements.logsRefresh?.addEventListener("click", () => void loadLogsPage(1));
      elements.eventsRefresh?.addEventListener("click", () => void loadEventsPage(1));
      elements.logsPrev?.addEventListener("click", () => void loadLogsPage(Math.max(1, state.logsPage.logsPage - 1)));
      elements.logsNext?.addEventListener("click", () => void loadLogsPage(state.logsPage.logsPage + 1));
      elements.eventsPrev?.addEventListener("click", () => void loadEventsPage(Math.max(1, state.logsPage.eventsPage - 1)));
      elements.eventsNext?.addEventListener("click", () => void loadEventsPage(state.logsPage.eventsPage + 1));
      elements.logsDownload?.addEventListener("click", downloadLogsPayload);
      elements.logsCopyVisible?.addEventListener("click", () => void copyVisibleLogsItems());
      elements.eventsCopyVisible?.addEventListener("click", () => void copyVisibleEventsItems());
      elements.logsSearch?.addEventListener("input", () => renderLogsPage(state.logsPage.latestLogsPayload || { items: [], total: 0, page: 1, has_next: false }));
      elements.eventsSearch?.addEventListener("input", () => renderEventsPage(state.logsPage.latestEventsPayload || { items: [], total: 0, page: 1, has_next: false }));
      elements.logsFilterSeverity?.addEventListener("change", () => {
        setSeverityChipActive(elements.logsFilterSeverity.value || "");
      });

      async function hydrateSelectedProject() {
        const token = beginProjectHydration();
        try {
          await loadThreadList(token);
        } catch (error) {
          if (isCurrentProjectHydrationToken(token)) {
            showToast(`載入 thread 清單失敗：${error.message}`, 9000, "warning");
          }
        }

        try {
          await loadProjectHistory(token);
        } catch (error) {
          if (isCurrentProjectHydrationToken(token)) {
            showToast(`載入歷史對話失敗：${error.message}`, 9000, "warning");
          }
        }

        if (!state.projectId || !isCurrentProjectHydrationToken(token)) return;

        try {
          await ensureActiveThread(token);
        } catch (error) {
          if (isCurrentProjectHydrationToken(token)) {
            showToast(`建立對話工作階段失敗：${error.message}`, 9000, "warning");
          }
        }

        try {
          await loadContext(token);
        } catch (error) {
          if (isCurrentProjectHydrationToken(token)) {
            showToast(`載入專案上下文失敗：${error.message}`, 9000, "warning");
          }
        }
      }

      elements.projectSelect.addEventListener("change", async (event) => {
        const selectedProject = event.target.value;
        await activateProject(selectedProject);
      });

      elements.createProjectBtn?.addEventListener("click", async () => {
        const name = window.prompt("請輸入專案名稱");
        if (name === null) return;
        const normalizedName = String(name || "").trim();
        if (!normalizedName) {
          showToast("專案名稱不可為空。", 7000, "warning");
          return;
        }
        try {
          const project = normalizeProjectRecord(await services.runs.createProject(normalizedName));
          await loadProjects();
          if (project?.project_id) {
            await activateProject(project.project_id);
          }
          showToast(`已建立專案：${normalizedName}`, 7000, "success");
        } catch (error) {
          showToast(`建立專案失敗：${error.message}`, 9000, "warning");
        }
      });

      elements.createThreadBtn?.addEventListener("click", async () => {
        const token = beginProjectHydration();
        try {
          await createThreadAndActivate(token);
        } catch (error) {
          if (isCurrentProjectHydrationToken(token)) {
            showToast(`建立 Thread 失敗：${error.message}`, 9000, "warning");
          }
        }
      });

      elements.refreshContext.addEventListener("click", loadContext);
      elements.planConfirm.addEventListener("click", () => confirmPlan(true));
      elements.planCancel.addEventListener("click", () => confirmPlan(false));
      elements.artifactsGoRun?.addEventListener("click", () => focusInspectorSection("execution"));
      elements.artifactsGoLogs?.addEventListener("click", () => navigateToRoute("logs"));
      elements.artifactsDownloadChat?.addEventListener("click", () => void downloadProjectHistory());
      elements.artifactPreviewClose?.addEventListener("click", closeArtifactPreview);
      elements.artifactPreviewModal?.addEventListener("click", (event) => {
        if (event.target === elements.artifactPreviewModal) closeArtifactPreview();
      });

      elements.copyRunId?.addEventListener("click", async () => {
        const runId = elements.copyRunId.dataset.runId;
        if (!runId) {
          showToast("目前沒有可複製的 Run ID。", 7000, "warning");
          return;
        }
        await copyText(runId, {
          toast: (message, options = {}) => showToast(message, options.duration || 7000, options.type || "success"),
          successMessage: "已複製完整 Run ID。",
          errorMessage: "複製失敗，請手動複製 Run ID。",
        });
      });


      elements.thinkingMode.addEventListener("change", (event) => {
        state.thinkingMode = event.target.value;
        updateThinking({ status: "idle", brief: "待命中；送出訊息後會顯示 Thinking 流程" });
      });

      (async () => {
        await runBootstrapInitialization({
          loadProjects,
          setProjectState,
          refreshUiPreferences,
          updateThinking,
          hydrateSelectedProject,
          resolveRouteFromHash,
          navigateToRoute,
          applyRoute,
          showToast,
          getProjectId: () => state.projectId,
          hasLocationHash: () => Boolean(window.location.hash),
        });
      })();

registerGlobalErrorHandlers();

// legacy smoke-test token: clearContextDraft("project")

}
