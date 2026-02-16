import { requestJson } from "./api.js";
import { createHashRouter } from "./router.js";
import { createStore } from "./state.js";
import { applyI18n } from "./i18n.js";
import { createToastManager } from "./ui/toast.js";
import { createConfirmModal } from "./ui/modal.js";

const { EventStreamClient, createUiEventStore } = window.AmonUIEventStream || {};
if (!EventStreamClient || !createUiEventStore) {
  throw new Error("AmonUIEventStream 尚未載入，請確認 /event_stream_client.js");
}
applyI18n(document);
const appStore = createStore({ locale: "zh-TW" });

      const state = {
        chatId: null,
        projectId: null,
        plan: null,
        streaming: false,
        attachments: [],
        uiStore: createUiEventStore(),
        streamClient: null,
        graph: null,
        graphRunId: null,
        graphNodeStates: {},
        graphEvents: [],
        graphSelectedNodeId: null,
        graphTemplateId: null,
        shellView: "chat",
        toolsCatalog: [],
        skillsCatalog: [],
        configView: null,
        logsPage: { logsPage: 1, eventsPage: 1, logsHasNext: false, eventsHasNext: false },
        billingSummary: null,
        billingStreamSource: null,
        contextPanelWidth: 320,
        runArtifacts: [],
        artifactPreviewItem: null,
        docsItems: [],
        docsFlatItems: [],
        docsFilteredItems: [],
        docsSelectedPath: null,
        docsFilterQuery: "",
        docsVirtual: { rowHeight: 40, buffer: 8 },
        thinkingMode: "brief",
        executionTimeline: new Map(),
        graphPanZoom: null,
        billRunChart: null,
      };

      const elements = {
        projectSelect: document.getElementById("project-select"),
        timeline: document.getElementById("timeline"),
        executionAccordion: document.getElementById("execution-accordion"),
        chatForm: document.getElementById("chat-form"),
        chatInput: document.getElementById("chat-input"),
        chatAttachments: document.getElementById("chat-attachments"),
        attachmentPreview: document.getElementById("attachment-preview"),
        toast: document.getElementById("toast"),
        confirmModal: document.getElementById("confirm-modal"),
        planCard: document.getElementById("plan-card"),
        planContent: document.getElementById("plan-content"),
        planCommands: document.getElementById("plan-commands"),
        planPatches: document.getElementById("plan-patches"),
        planRisk: document.getElementById("plan-risk"),
        planConfirm: document.getElementById("plan-confirm"),
        planCancel: document.getElementById("plan-cancel"),
        refreshContext: document.getElementById("refresh-context"),
        graphPreview: document.getElementById("graph-preview"),
        graphCode: document.getElementById("graph-code"),
        graphNodeList: document.getElementById("graph-node-list"),
        graphRunMeta: document.getElementById("graph-run-meta"),
        copyRunId: document.getElementById("copy-run-id"),
        graphCreateTemplate: document.getElementById("graph-create-template"),
        graphNodeDrawer: document.getElementById("graph-node-drawer"),
        graphNodeClose: document.getElementById("graph-node-close"),
        graphNodeTitle: document.getElementById("graph-node-title"),
        graphNodeMeta: document.getElementById("graph-node-meta"),
        graphNodeInputs: document.getElementById("graph-node-inputs"),
        graphNodeOutputs: document.getElementById("graph-node-outputs"),
        graphNodeEvents: document.getElementById("graph-node-events"),
        graphParametrize: document.getElementById("graph-parametrize"),
        chatProjectLabel: document.getElementById("chat-project-label"),
        contextProject: document.getElementById("context-project"),
        contextOverview: document.getElementById("context-overview"),
        contextTabs: document.querySelectorAll(".context-tab"),
        contextPanels: document.querySelectorAll("[data-context-panel]"),
        streamProgress: document.getElementById("stream-progress"),
        chatLayout: document.getElementById("chat-layout"),
        contextPage: document.getElementById("context-page"),
        graphPage: document.getElementById("graph-page"),
        uiShell: document.getElementById("ui-shell"),
        toggleSidebar: document.getElementById("toggle-sidebar"),
        toggleContextPanel: document.getElementById("toggle-context-panel"),
        contextPanel: document.getElementById("context-panel"),
        contextResizer: document.getElementById("context-resizer"),
        shellRunStatus: document.getElementById("shell-run-status"),
        shellDaemonStatus: document.getElementById("shell-daemon-status"),
        shellBudgetStatus: document.getElementById("shell-budget-status"),
        cardRunProgress: document.getElementById("card-run-progress"),
        cardBilling: document.getElementById("card-billing"),
        cardPendingConfirmations: document.getElementById("card-pending-confirmations"),
        thinkingMode: document.getElementById("thinking-mode"),
        thinkingSummary: document.getElementById("thinking-summary"),
        thinkingDetail: document.getElementById("thinking-detail"),
        artifactList: document.getElementById("artifact-list"),
        artifactsOverview: document.getElementById("artifacts-overview"),
        artifactsInspectorList: document.getElementById("artifacts-inspector-list"),
        artifactsEmpty: document.getElementById("artifacts-empty"),
        artifactsGoRun: document.getElementById("artifacts-go-run"),
        artifactsGoLogs: document.getElementById("artifacts-go-logs"),
        artifactPreviewModal: document.getElementById("artifact-preview-modal"),
        artifactPreviewTitle: document.getElementById("artifact-preview-title"),
        artifactPreviewBody: document.getElementById("artifact-preview-body"),
        artifactPreviewClose: document.getElementById("artifact-preview-close"),
        artifactPreviewDownload: document.getElementById("artifact-preview-download"),
        artifactPreviewCopy: document.getElementById("artifact-preview-copy"),
        shellNavItems: document.querySelectorAll(".shell-nav__link"),
        toolsSkillsPage: document.getElementById("tools-skills-page"),
        billPage: document.getElementById("bill-page"),
        billRefresh: document.getElementById("bill-refresh"),
        billToday: document.getElementById("bill-today"),
        billProjectTotal: document.getElementById("bill-project-total"),
        billModeSummary: document.getElementById("bill-mode-summary"),
        billCurrentRun: document.getElementById("bill-current-run"),
        billRunChart: document.getElementById("bill-run-chart"),
        billBudgets: document.getElementById("bill-budgets"),
        billExceeded: document.getElementById("bill-exceeded"),
        billBreakdownProvider: document.getElementById("bill-breakdown-provider"),
        billBreakdownModel: document.getElementById("bill-breakdown-model"),
        billBreakdownAgent: document.getElementById("bill-breakdown-agent"),
        billBreakdownNode: document.getElementById("bill-breakdown-node"),
        toolsSkillsRefresh: document.getElementById("tools-skills-refresh"),
        toolsList: document.getElementById("tools-list"),
        skillsList: document.getElementById("skills-list"),
        skillsCollisions: document.getElementById("skills-collisions"),
        skillTriggerSelect: document.getElementById("skill-trigger-select"),
        skillTriggerPreview: document.getElementById("skill-trigger-preview"),
        skillInjectionPreview: document.getElementById("skill-injection-preview"),
        configPage: document.getElementById("config-page"),
        logsEventsPage: document.getElementById("logs-events-page"),
        docsPage: document.getElementById("docs-page"),
        docsRefresh: document.getElementById("docs-refresh"),
        docsTreeMeta: document.getElementById("docs-tree-meta"),
        docsFilter: document.getElementById("docs-filter"),
        docsTreeViewport: document.getElementById("docs-tree-viewport"),
        docsPreviewTitle: document.getElementById("docs-preview-title"),
        docsPreviewMeta: document.getElementById("docs-preview-meta"),
        docsPreviewContent: document.getElementById("docs-preview-content"),
        docsOpen: document.getElementById("docs-open"),
        docsDownload: document.getElementById("docs-download"),
        docsInsert: document.getElementById("docs-insert"),
        logsSource: document.getElementById("logs-source"),
        logsTimeFrom: document.getElementById("logs-time-from"),
        logsTimeTo: document.getElementById("logs-time-to"),
        logsFilterProject: document.getElementById("logs-filter-project"),
        logsFilterRun: document.getElementById("logs-filter-run"),
        logsFilterNode: document.getElementById("logs-filter-node"),
        logsFilterSeverity: document.getElementById("logs-filter-severity"),
        logsFilterComponent: document.getElementById("logs-filter-component"),
        logsRefresh: document.getElementById("logs-refresh"),
        logsDownload: document.getElementById("logs-download"),
        logsSummary: document.getElementById("logs-summary"),
        logsList: document.getElementById("logs-list"),
        logsPrev: document.getElementById("logs-prev"),
        logsNext: document.getElementById("logs-next"),
        logsPageLabel: document.getElementById("logs-page-label"),
        eventsFilterType: document.getElementById("events-filter-type"),
        eventsTimeFrom: document.getElementById("events-time-from"),
        eventsTimeTo: document.getElementById("events-time-to"),
        eventsFilterProject: document.getElementById("events-filter-project"),
        eventsFilterRun: document.getElementById("events-filter-run"),
        eventsFilterNode: document.getElementById("events-filter-node"),
        eventsRefresh: document.getElementById("events-refresh"),
        eventsSummary: document.getElementById("events-summary"),
        eventsList: document.getElementById("events-list"),
        eventsPrev: document.getElementById("events-prev"),
        eventsNext: document.getElementById("events-next"),
        eventsPageLabel: document.getElementById("events-page-label"),
        configRefresh: document.getElementById("config-refresh"),
        configSearch: document.getElementById("config-search"),
        configExport: document.getElementById("config-export"),
        configGlobal: document.getElementById("config-global"),
        configProject: document.getElementById("config-project"),
        configEffectiveSummary: document.getElementById("config-effective-summary"),
        configTableBody: document.getElementById("config-table-body"),
        contextDraftInput: document.getElementById("context-draft-input"),
        contextDraftMeta: document.getElementById("context-draft-meta"),
        contextSaveDraft: document.getElementById("context-save-draft"),
        contextImportFile: document.getElementById("context-import-file"),
        contextExtractChat: document.getElementById("context-extract-chat"),
        contextClearChat: document.getElementById("context-clear-chat"),
        contextClearProject: document.getElementById("context-clear-project"),
      };

      const toastManager = createToastManager(elements.toast);
      const confirmModal = createConfirmModal(elements.confirmModal);

      const STORAGE_KEYS = {
        contextCollapsed: "amon.ui.contextPanelCollapsed",
        contextWidth: "amon.ui.contextPanelWidth",
        contextDraftPrefix: "amon.ui.contextDraft:",
      };

      function readStorage(key) {
        try {
          return window.localStorage.getItem(key);
        } catch (error) {
          return null;
        }
      }

      function writeStorage(key, value) {
        try {
          window.localStorage.setItem(key, value);
        } catch (error) {
          console.warn("storage_write_failed", key, error);
        }
      }

      function safeRemoveStorage(key) {
        try {
          window.localStorage.removeItem(key);
        } catch (error) {
          console.warn("storage_remove_failed", key, error);
        }
      }

      function formatUnknownValue(value, fallback = "尚未取得資料") {
        if (value === null || value === undefined) return fallback;
        const text = String(value).trim();
        if (!text || text === "--" || text.toLowerCase() === "unknown") {
          return fallback;
        }
        return text;
      }

      function shortenId(value, front = 6, back = 4) {
        const text = String(value || "");
        if (!text) return "尚未有 Run";
        if (text.length <= front + back + 1) return text;
        return `${text.slice(0, front)}…${text.slice(-back)}`;
      }

      function applyPillClass(element, level = "neutral") {
        if (!element) return;
        element.classList.remove("pill--success", "pill--warning", "pill--danger", "pill--neutral");
        element.classList.add(`pill--${level}`);
      }

      function setStatusText(element, text, level = "neutral", tooltip = "") {
        if (!element) return;
        element.textContent = text;
        if (tooltip) {
          element.title = tooltip;
        }
        applyPillClass(element, level);
      }

      function mapRunStatusLevel(status = "idle") {
        const key = String(status || "").toLowerCase();
        if (["ok", "success", "succeeded", "completed"].includes(key)) return "success";
        if (["error", "failed", "unavailable"].includes(key)) return "danger";
        if (["confirm_required", "warning", "degraded"].includes(key)) return "warning";
        return "neutral";
      }

      function mapDaemonStatusLevel(status = "idle") {
        const key = String(status || "").toLowerCase();
        if (["connected", "healthy"].includes(key)) return "success";
        if (["reconnecting"].includes(key)) return "warning";
        if (["error", "unavailable", "disconnected"].includes(key)) return "danger";
        return "neutral";
      }

      function getContextDraftStorageKey(projectId = state.projectId) {
        const scope = projectId || "no-project";
        return `${STORAGE_KEYS.contextDraftPrefix}${scope}`;
      }

      function syncContextPanelToggle() {
        if (!elements.uiShell || !elements.toggleContextPanel) {
          return;
        }
        const collapsed = elements.uiShell.classList.contains("is-context-collapsed");
        elements.toggleContextPanel.textContent = collapsed ? "展開右側面板" : "收合右側面板";
        elements.toggleContextPanel.setAttribute("aria-expanded", String(!collapsed));
        writeStorage(STORAGE_KEYS.contextCollapsed, collapsed ? "1" : "0");
      }

      function applyContextPanelWidth(width) {
        const clamped = Math.max(280, Math.min(520, Number(width) || 320));
        state.contextPanelWidth = clamped;
        elements.chatLayout?.style.setProperty("--context-panel-width", `${clamped}px`);
        writeStorage(STORAGE_KEYS.contextWidth, String(clamped));
      }

      function restoreContextPanelState() {
        const collapsed = readStorage(STORAGE_KEYS.contextCollapsed) === "1";
        elements.uiShell?.classList.toggle("is-context-collapsed", collapsed);
        const storedWidth = Number(readStorage(STORAGE_KEYS.contextWidth));
        if (Number.isFinite(storedWidth) && storedWidth > 0) {
          applyContextPanelWidth(storedWidth);
        } else {
          applyContextPanelWidth(320);
        }
        syncContextPanelToggle();
      }

      function setupContextResizer() {
        if (!elements.contextResizer || !elements.chatLayout || !elements.contextPanel) {
          return;
        }
        let dragging = false;
        const onMove = (event) => {
          if (!dragging) return;
          const layoutRect = elements.chatLayout.getBoundingClientRect();
          const width = layoutRect.right - event.clientX;
          applyContextPanelWidth(width);
        };
        const onUp = () => {
          dragging = false;
          document.body.classList.remove("is-resizing-context-panel");
        };
        elements.contextResizer.addEventListener("mousedown", (event) => {
          event.preventDefault();
          dragging = true;
          document.body.classList.add("is-resizing-context-panel");
        });
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
      }

      elements.toggleContextPanel?.addEventListener("click", () => {
        if (window.innerWidth <= 1200) {
          elements.uiShell?.classList.toggle("is-context-drawer-open");
        } else {
          elements.uiShell?.classList.toggle("is-context-collapsed");
        }
        syncContextPanelToggle();
      });

      elements.toggleSidebar?.addEventListener("click", () => {
        elements.uiShell?.classList.toggle("is-sidebar-collapsed");
      });

      restoreContextPanelState();
      setupContextResizer();
      setStatusText(elements.shellDaemonStatus, "Daemon：尚未連線", "neutral", "尚未建立串流連線");
      setStatusText(elements.shellRunStatus, "Run：尚未有 Run", "neutral", "目前尚未執行任何 Run");

      const routeToShellView = {
        chat: "chat",
        context: "context",
        graph: "graph",
        tools: "tools-skills",
        config: "config",
        logs: "logs-events",
        docs: "docs",
        billing: "bill",
      };

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

      function setActiveShellNav(routeKey) {
        elements.shellNavItems.forEach((item) => {
          const isActive = item.dataset.route === routeKey;
          item.classList.toggle("is-active", isActive);
          item.setAttribute("aria-current", isActive ? "page" : "false");
        });
      }

      function switchShellView(view) {
        if (view !== "bill") {
          closeBillingStream();
        }
        state.shellView = view;
        elements.chatLayout.hidden = view !== "chat";
        elements.contextPage.hidden = view !== "context";
        elements.graphPage.hidden = view !== "graph";
        elements.toolsSkillsPage.hidden = view !== "tools-skills";
        elements.billPage.hidden = view !== "bill";
        elements.configPage.hidden = view !== "config";
        elements.logsEventsPage.hidden = view !== "logs-events";
        elements.docsPage.hidden = view !== "docs";
        if (view !== "chat") elements.uiShell?.classList.remove("is-context-drawer-open");
      }

      async function loadShellViewDependencies(view) {
        if (view === "tools-skills") {
          await loadToolsSkillsPage();
        }
        if (view === "config") {
          await loadConfigPage();
        }
        if (view === "logs-events") {
          await loadLogsEventsPage();
        }
        if (view === "docs") {
          await loadDocsPage();
        }
        if (view === "bill") {
          await loadBillPage();
        }
      }

      async function applyRoute(routeKey) {
        const view = routeToShellView[routeKey] || "chat";
        switchShellView(view);
        setActiveShellNav(routeKey);
        await loadShellViewDependencies(view);
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
          return;
        }
        elements.configGlobal.textContent = JSON.stringify(payload.global_config || {}, null, 2);
        elements.configProject.textContent = JSON.stringify(payload.project_config || {}, null, 2);

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
          `;
          elements.configTableBody.appendChild(tr);
        });
      }

      async function loadConfigPage() {
        const projectParam = state.projectId ? `?project_id=${encodeURIComponent(state.projectId)}` : "";
        const payload = await apiFetch(`/config/view${projectParam}`);
        state.configView = payload;
        renderConfigTable();
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
        const projectParam = state.projectId ? `?project_id=${encodeURIComponent(state.projectId)}` : "";
        const payload = await apiFetch(`/billing/summary${projectParam}`);
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
        elements.logsList.innerHTML = "";
        elements.logsSummary.textContent = `共 ${payload.total} 筆，顯示第 ${payload.page} 頁。`;
        elements.logsPageLabel.textContent = `第 ${payload.page} 頁`;
        elements.logsPrev.disabled = payload.page <= 1;
        elements.logsNext.disabled = !payload.has_next;
        payload.items.forEach((item) => {
          const card = document.createElement("article");
          card.className = "log-item";
          card.innerHTML = `
            <header><strong>${escapeHtml(item.level || item.severity || "INFO")}</strong> · <code>${escapeHtml(item.ts || "-")}</code></header>
            <div class="log-item__meta">${escapeHtml(item.project_id || "-")} / ${escapeHtml(item.run_id || "-")} / ${escapeHtml(item.node_id || "-")}</div>
            <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
          `;
          elements.logsList.appendChild(card);
        });
        if (!payload.items.length) {
          elements.logsList.textContent = "查無資料";
        }
      }

      function renderEventsPage(payload) {
        elements.eventsList.innerHTML = "";
        elements.eventsSummary.textContent = `共 ${payload.total} 筆，顯示第 ${payload.page} 頁。`;
        elements.eventsPageLabel.textContent = `第 ${payload.page} 頁`;
        elements.eventsPrev.disabled = payload.page <= 1;
        elements.eventsNext.disabled = !payload.has_next;
        payload.items.forEach((item) => {
          const card = document.createElement("article");
          card.className = "log-item";
          const eventType = item.event || item.type || "unknown";
          card.innerHTML = `
            <header><strong>${escapeHtml(eventType)}</strong> · <code>${escapeHtml(item.ts || "-")}</code></header>
            <div class="log-item__meta">${escapeHtml(item.project_id || "-")} / ${escapeHtml(item.run_id || "-")} / ${escapeHtml(item.node_id || "-")}</div>
            <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
          `;
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
          card.appendChild(drilldown);
          elements.eventsList.appendChild(card);
        });
        if (!payload.items.length) {
          elements.eventsList.textContent = "查無資料";
        }
      }

      async function loadLogsPage(page = 1) {
        const payload = await apiFetch(`/logs/query?${buildLogsQuery(page).toString()}`);
        state.logsPage.logsPage = payload.page;
        state.logsPage.logsHasNext = payload.has_next;
        renderLogsPage(payload);
      }

      async function loadEventsPage(page = 1) {
        const payload = await apiFetch(`/events/query?${buildEventsQuery(page).toString()}`);
        state.logsPage.eventsPage = payload.page;
        state.logsPage.eventsHasNext = payload.has_next;
        renderEventsPage(payload);
      }

      async function loadLogsEventsPage() {
        if (!elements.logsFilterProject.value && state.projectId) {
          elements.logsFilterProject.value = state.projectId;
        }
        if (!elements.eventsFilterProject.value && state.projectId) {
          elements.eventsFilterProject.value = state.projectId;
        }
        await Promise.all([loadLogsPage(1), loadEventsPage(1)]);
      }

      async function loadToolsSkillsPage() {
        const projectParam = state.projectId ? `?project_id=${encodeURIComponent(state.projectId)}` : "";
        const toolsPayload = await apiFetch(`/tools/catalog${projectParam}`);
        const skillsPayload = await apiFetch(`/skills/catalog${projectParam}`);
        state.toolsCatalog = toolsPayload.tools || [];
        state.skillsCatalog = skillsPayload.skills || [];
        renderToolsList(state.toolsCatalog, toolsPayload.policy_editable);
        renderSkillsList(state.skillsCatalog, skillsPayload.collisions || []);
      }

      function formatRecentUsage(usage) {
        if (!usage || !usage.ts_ms) return "尚無紀錄";
        const dt = new Date(usage.ts_ms);
        return `${dt.toLocaleString("zh-TW", { hour12: false })} (${usage.decision || "unknown"})`;
      }

      function renderSchema(schema) {
        return `<pre>${escapeHtml(JSON.stringify(schema || {}, null, 2))}</pre>`;
      }

      function queueToolPolicyPlan(toolName, action, requireConfirm) {
        apiFetch("/tools/policy/plan", {
          method: "POST",
          body: JSON.stringify({ tool_name: toolName, action, require_confirm: requireConfirm }),
        })
          .then((payload) => {
            showPlanCard({
              ...payload.plan,
              confirm_api: "/tools/policy/confirm",
            });
          })
          .catch((error) => showToast(`建立 Plan Card 失敗：${error.message}`));
      }

      function renderToolsList(tools = [], policyEditable = false) {
        elements.toolsList.innerHTML = "";
        if (!tools.length) {
          elements.toolsList.innerHTML = '<p class="empty-context">尚未找到工具。</p>';
          return;
        }
        tools.forEach((tool) => {
          const card = document.createElement("article");
          card.className = "tool-card";
          card.innerHTML = `
            <header>
              <div>
                <strong>${escapeHtml(tool.name)}</strong>
                <p>${escapeHtml(tool.type)} ｜ v${escapeHtml(String(tool.version || "unknown"))}</p>
              </div>
              <span class="risk-chip">risk: ${escapeHtml(String(tool.risk || "unknown"))}</span>
            </header>
            <p>allowed_paths：${escapeHtml((tool.allowed_paths || []).join(", ") || "workspace")}</p>
            <p>預設策略：<strong>${escapeHtml(String(tool.policy_decision || "deny").toUpperCase())}</strong></p>
            <p>策略說明：${escapeHtml(tool.policy_reason || "未命中 allow 規則，預設拒絕")}</p>
            <p>最近使用：${escapeHtml(formatRecentUsage(tool.recent_usage))}</p>
            <details><summary>inputs schema</summary>${renderSchema(tool.input_schema)}</details>
            <details><summary>outputs schema</summary>${renderSchema(tool.output_schema)}</details>
          `;
          const actions = document.createElement("div");
          actions.className = "tool-card__actions";
          if (policyEditable) {
            const enableButton = document.createElement("button");
            enableButton.type = "button";
            enableButton.className = "secondary-btn small";
            enableButton.textContent = tool.enabled ? "Disable" : "Enable";
            enableButton.addEventListener("click", () => queueToolPolicyPlan(tool.name, tool.enabled ? "disable" : "enable", Boolean(tool.require_confirm)));
            actions.appendChild(enableButton);

            const confirmButton = document.createElement("button");
            confirmButton.type = "button";
            confirmButton.className = "secondary-btn small";
            confirmButton.textContent = `Require Confirm：${tool.require_confirm ? "ON" : "OFF"}`;
            confirmButton.addEventListener("click", () => queueToolPolicyPlan(tool.name, "require_confirm", !tool.require_confirm));
            actions.appendChild(confirmButton);
          }
          card.appendChild(actions);
          elements.toolsList.appendChild(card);
        });
      }

      function renderSkillsList(skills = [], collisions = []) {
        elements.skillsList.innerHTML = "";
        elements.skillsCollisions.innerHTML = "";
        if (collisions.length) {
          collisions.forEach((item) => {
            const tip = document.createElement("p");
            tip.className = "collision-tip";
            tip.textContent = `⚠️ ${item.name}：${item.message}`;
            elements.skillsCollisions.appendChild(tip);
          });
        }
        if (!skills.length) {
          elements.skillsList.innerHTML = '<p class="empty-context">尚未找到 skills。</p>';
          return;
        }
        elements.skillTriggerSelect.innerHTML = "";
        skills.forEach((skill) => {
          const card = document.createElement("article");
          card.className = "skill-card";
          const frontmatter = skill.frontmatter || {};
          card.innerHTML = `
            <header><strong>${escapeHtml(skill.name || "(未命名)")}</strong><span>${escapeHtml(skill.source || "unknown")}</span></header>
            <p>${escapeHtml(frontmatter.description || skill.description || "無描述")}</p>
            <p class="skill-source">來源：${escapeHtml(skill.path || "")}</p>
            <pre>${escapeHtml(JSON.stringify({ name: frontmatter.name || skill.name, description: frontmatter.description || "" }, null, 2))}</pre>
          `;
          elements.skillsList.appendChild(card);

          const option = document.createElement("option");
          option.value = skill.name || "";
          option.textContent = `${skill.name || "(未命名)"}（${skill.source || "unknown"}）`;
          elements.skillTriggerSelect.appendChild(option);
        });
      }

      function showToast(message, duration = 9000, type = "info") {
        toastManager.show(message, { duration, type });
      }

      window.amonUiDebug = {
        showToast,
        showConfirmModal: (options) => confirmModal.open(options),
      };

      function renderStoreSummary(storeState) {
        const runStatus = formatUnknownValue(storeState.run?.status || (state.streaming ? "running" : "idle"), "尚未有 Run");
        const runProgress = storeState.run?.progress;
        if (!elements.shellRunStatus || !elements.cardRunProgress || !elements.cardBilling || !elements.shellBudgetStatus || !elements.cardPendingConfirmations) {
          return;
        }
        setStatusText(elements.shellRunStatus, `Run：${runStatus}`, mapRunStatusLevel(runStatus), `目前執行狀態：${runStatus}`);
        elements.cardRunProgress.textContent = Number.isFinite(runProgress) ? `${runProgress}%` : "尚未有 Run";
        elements.cardRunProgress.title = Number.isFinite(runProgress) ? "目前 Run 進度" : "尚未有 Run 可顯示進度";
        elements.cardBilling.textContent = `NT$ ${Number(storeState.billing.total_cost || 0).toFixed(2)}`;
        elements.cardBilling.title = "目前已累計費用";
        elements.shellBudgetStatus.textContent = `Budget：NT$ ${Number(storeState.billing.total_cost || 0).toFixed(2)} / NT$ 5,000`;
        const pendingJobs = Object.values(storeState.jobs).filter((job) => job.status && job.status !== "completed").length;
        elements.cardPendingConfirmations.textContent = pendingJobs > 0 ? `${pendingJobs} 項任務進行中` : "0 項";
        elements.cardPendingConfirmations.title = pendingJobs > 0 ? "仍有任務等待確認或完成" : "目前沒有待確認任務";
      }

      state.uiStore.subscribe((snapshot) => {
        renderStoreSummary(snapshot);
        if (snapshot.docs.length > 0) {
          renderDocs(snapshot.docs);
        }
      });
      renderStoreSummary(state.uiStore.getState());

      async function apiFetch(path, options = {}) {
        const response = await fetch(`/v1${path}`, {
          headers: { "Content-Type": "application/json" },
          ...options,
        });
        let payload = {};
        try {
          payload = await response.json();
        } catch (error) {
          payload = {};
        }
        if (!response.ok) {
          throw new Error(payload.message || "API 發生錯誤");
        }
        return payload;
      }

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
          updateExecutionStep("node_status", { title: "Node 狀態", status: data.status === "ok" ? "succeeded" : "running", details: state.graphRunId ? `Run ${shortenId(state.graphRunId)} 已更新` : "等待下一次 context refresh", inferred: true });
          return;
        }
        if (eventType === "error") {
          updateExecutionStep("tool_execution", { title: "Tool execution", status: "failed", details: data.message || "執行時發生錯誤", inferred: false });
        }
      }

      function appendRestoredMessage(role, text, ts = "") {
        const row = document.createElement("article");
        row.className = "timeline-row";

        const bubble = document.createElement("div");
        bubble.className = `chat-bubble ${role}`;
        const prefix = role === "user" ? "你：" : "Amon：";
        bubble.innerHTML = renderMarkdown(`${prefix}${text}`);

        const footer = document.createElement("footer");
        footer.className = "timeline-meta";
        const roleLabel = role === "user" ? "你" : "Amon";
        footer.textContent = ts ? `${ts}・${roleLabel}` : roleLabel;

        row.appendChild(bubble);
        row.appendChild(footer);
        elements.timeline.appendChild(row);
      }

      async function loadProjectHistory() {
        elements.timeline.innerHTML = "";
        if (!state.projectId) {
          appendTimelineStatus("目前為無專案模式。輸入任務後會自動建立新專案並切換。");
          return;
        }
        const payload = await apiFetch(`/projects/${encodeURIComponent(state.projectId)}/chat-history`);
        state.chatId = payload.chat_id || state.chatId;
        const messages = Array.isArray(payload.messages) ? payload.messages : [];
        if (!messages.length) {
          appendTimelineStatus("目前尚無歷史對話。請直接輸入需求開始。");
          return;
        }
        messages.forEach((item) => {
          const role = item.role === "user" ? "user" : "agent";
          appendRestoredMessage(role, item.text || "", item.ts || "");
        });
        elements.timeline.scrollTop = elements.timeline.scrollHeight;
      }

      function collectArtifactsFromNodeStates(nodeStates = {}) {
        const artifacts = [];
        Object.entries(nodeStates || {}).forEach(([nodeId, nodeState]) => {
          const output = nodeState && typeof nodeState === "object" ? nodeState.output : null;
          if (!output || typeof output !== "object") {
            return;
          }
          const entries = [];
          if (Array.isArray(output.artifacts)) {
            entries.push(...output.artifacts);
          }
          if (Array.isArray(output.docs)) {
            entries.push(...output.docs);
          }
          if (typeof output.path === "string") {
            entries.push({ path: output.path });
          }
          entries.forEach((item) => {
            if (typeof item === "string") {
              artifacts.push({ type: "artifact", run_id: state.graphRunId || "尚未取得 Run ID", node_id: nodeId, path: item, preview: "" });
              return;
            }
            if (item && typeof item === "object" && item.path) {
              artifacts.push({
                type: item.type || "artifact",
                run_id: item.run_id || state.graphRunId || "尚未取得 Run ID",
                node_id: item.node_id || nodeId,
                path: item.path,
                preview: item.preview || "",
              });
            }
          });
        });
        return artifacts;
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
        elements.chatInput.disabled = active;
      }

      function resetPlanCard() {
        state.plan = null;
        elements.planCard.hidden = true;
        elements.planContent.textContent = "";
        elements.planCommands.innerHTML = "";
        elements.planPatches.innerHTML = "";
        elements.planRisk.innerHTML = "";
      }

      function setProjectState(projectId) {
        state.projectId = projectId || null;
        elements.refreshContext.disabled = !state.projectId;
        if (state.projectId && !elements.projectSelect.querySelector(`option[value="${CSS.escape(state.projectId)}"]`)) {
          const dynamicOption = document.createElement("option");
          dynamicOption.value = state.projectId;
          dynamicOption.textContent = `新專案（${state.projectId}）`;
          dynamicOption.dataset.dynamic = "true";
          elements.projectSelect.appendChild(dynamicOption);
        }
        elements.projectSelect.value = projectId || "";
        syncContextHeader();
        refreshContextDraftUi();
        if (!state.projectId) {
          state.chatId = null;
          elements.timeline.innerHTML = "";
          renderArtifacts([]);
          renderArtifactsInspector([]);
          elements.graphPreview.innerHTML = "<p class=\"empty-context\">請先在上方選擇專案。</p>";
          elements.graphCode.textContent = "";
          elements.contextOverview.textContent = "請先在上方選擇專案，右側內容會自動同步。";
          elements.graphRunMeta.textContent = "尚未偵測到 Run";
          elements.copyRunId.disabled = true;
        }
      }

      function syncContextHeader() {
        const selected = elements.projectSelect.selectedOptions[0]?.textContent || "未指定專案";
        elements.contextProject.textContent = `目前專案：${selected}`;
        elements.chatProjectLabel.textContent = `目前專案：${selected}`;
      }

      function switchContextTab(tabName) {
        elements.contextTabs.forEach((tab) => {
          const isActive = tab.dataset.contextTab === tabName;
          tab.classList.toggle("is-active", isActive);
          tab.setAttribute("aria-selected", String(isActive));
        });
        elements.contextPanels.forEach((panel) => {
          panel.hidden = panel.dataset.contextPanel !== tabName;
        });
      }

      function refreshContextDraftUi() {
        const draftKey = getContextDraftStorageKey();
        const draftText = readStorage(draftKey) || "";
        elements.contextDraftInput.value = draftText;
        if (draftText.trim()) {
          elements.contextDraftMeta.textContent = state.projectId
            ? `已載入專案 ${state.projectId} 的本機草稿。`
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
        showToast(text ? "Context 草稿已儲存（僅本機）。" : "已清空本機草稿。", 9000, "success");
      }

      async function clearContextDraft(scope = "chat") {
        const title = scope === "project" ? "清空專案 Context 草稿" : "清空本次對話 Context 草稿";
        const description = scope === "project"
          ? "將刪除目前專案在此瀏覽器的 Context 草稿。此動作只影響本機，不會刪除伺服器資料，且不可復原。"
          : "將刪除目前對話在此瀏覽器的 Context 草稿。此動作只影響本機，不會刪除伺服器資料，且不可復原。";
        const confirmed = await confirmModal.open({
          title,
          description,
          confirmText: "確認清空",
          cancelText: "取消",
        });
        if (!confirmed) {
          showToast("已取消清空 Context。", 5000, "neutral");
          return;
        }
        const key = getContextDraftStorageKey(scope === "project" ? state.projectId : null);
        safeRemoveStorage(key);
        if (scope === "project") {
          refreshContextDraftUi();
        } else {
          elements.contextDraftInput.value = "";
          elements.contextDraftMeta.textContent = "已清空本次對話 Context 草稿。";
        }
        showToast("已清空 Context 草稿（僅本機）。", 9000, "success");
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
        showToast("已從最近對話擷取 Context 草稿。", 9000, "success");
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

      async function loadProjects() {
        let projects = [];
        try {
          const payload = await apiFetch("/projects");
          projects = payload.projects || [];
        } catch (error) {
          throw error;
        }
        elements.projectSelect.innerHTML = "";
        const emptyOption = document.createElement("option");
        emptyOption.value = "";
        emptyOption.textContent = "無專案";
        elements.projectSelect.appendChild(emptyOption);
        projects.forEach((project) => {
          const option = document.createElement("option");
          option.value = project.project_id;
          option.textContent = `${project.name}（${project.project_id}）`;
          elements.projectSelect.appendChild(option);
        });
        const availableIds = new Set(projects.map((project) => project.project_id));
        if (state.projectId && !availableIds.has(state.projectId)) {
          state.projectId = null;
        }
        elements.projectSelect.value = state.projectId || "";
        syncContextHeader();
        if (!projects.length) {
          showToast("尚無專案，請在聊天輸入：建立專案 <名稱>");
        }
        elements.refreshContext.disabled = !state.projectId;
      }

      async function ensureChatSession() {
        if (!state.projectId) return;
        const payload = await apiFetch("/chat/sessions", {
          method: "POST",
          body: JSON.stringify({ project_id: state.projectId }),
        });
        state.chatId = payload.chat_id;
      }

      async function loadContext() {
        if (!state.projectId) {
          showToast("請先選擇專案。");
          return;
        }
        const payload = await apiFetch(`/projects/${encodeURIComponent(state.projectId)}/context`);
        state.graph = payload.graph || { nodes: [], edges: [] };
        state.graphRunId = payload.run_id || null;
        state.graphNodeStates = payload.node_states || {};
        state.graphEvents = payload.recent_events || [];
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
        renderArtifacts(collectArtifactsFromNodeStates(state.graphNodeStates));
        const nodeStatuses = Object.values(state.graphNodeStates || {}).map((node) => normalizeNodeStatus(node?.status));
        const hasFailedNode = nodeStatuses.includes("failed");
        const hasRunningNode = nodeStatuses.includes("running");
        updateExecutionStep("node_status", {
          title: "Node 狀態",
          status: hasFailedNode ? "failed" : hasRunningNode ? "running" : nodeStatuses.length ? "succeeded" : "pending",
          details: nodeStatuses.length ? `共 ${nodeStatuses.length} 個節點狀態已同步` : "尚無節點事件",
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
          const payload = await apiFetch(`/projects/${encodeURIComponent(state.projectId)}/docs/content?path=${encodeURIComponent(selected.path)}`);
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
        const payload = await apiFetch(`/projects/${encodeURIComponent(state.projectId)}/docs`);
        const docs = (payload.docs || []).map(normalizeDocItem);
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
        if (!code) return;
        try {
          const { svg } = await window.__mermaid.render(`graphPreview-${Date.now()}`, code);
          elements.graphPreview.innerHTML = svg;
          const svgEl = elements.graphPreview.querySelector("svg");
          if (svgEl && window.svgPanZoom) {
            state.graphPanZoom = svgPanZoom(svgEl, {
              controlIconsEnabled: true,
              fit: true,
              center: true,
              zoomScaleSensitivity: 0.35,
              minZoom: 0.5,
              maxZoom: 6,
            });
          }
          decorateMermaidNodes();
        } catch (error) {
          elements.graphPreview.innerHTML = "<p>Mermaid 渲染失敗，請檢查 graph。</p>";
        }
      }

      function normalizeNodeStatus(status) {
        if (status === "completed") return "succeeded";
        if (["pending", "running", "failed", "succeeded"].includes(status)) return status;
        return "pending";
      }

      function getNodeState(nodeId) {
        return state.graphNodeStates?.[nodeId] || { status: "pending" };
      }

      function nodeStatusLabel(status) {
        const normalized = normalizeNodeStatus(status);
        if (normalized === "running") return "執行中";
        if (normalized === "succeeded") return "成功";
        if (normalized === "failed") return "失敗";
        return "等待中";
      }

      function renderNodeList() {
        elements.graphNodeList.innerHTML = "";
        const nodes = state.graph?.nodes || [];
        if (!nodes.length) return;
        nodes.forEach((node) => {
          const stateItem = getNodeState(node.id);
          const status = normalizeNodeStatus(stateItem.status);
          const item = document.createElement("li");
          item.className = "graph-node-item";
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "graph-node-item__button";
          btn.innerHTML = `<span>${node.id}</span><span class="node-status node-status--${status}">${nodeStatusLabel(status)}</span>`;
          btn.addEventListener("click", () => openNodeDrawer(node.id));
          item.appendChild(btn);
          elements.graphNodeList.appendChild(item);
        });
      }

      function decorateMermaidNodes() {
        const groups = elements.graphPreview.querySelectorAll("g.node");
        groups.forEach((group) => {
          const label = group.querySelector(".nodeLabel")?.textContent?.trim();
          if (!label) return;
          const status = normalizeNodeStatus(getNodeState(label).status);
          group.classList.add(`node-status--${status}`);
          group.style.cursor = "pointer";
          group.addEventListener("click", () => openNodeDrawer(label));
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
        const nodeState = getNodeState(nodeId);
        const executionEngine = node.type && String(node.type).includes("tool") ? "tool" : "llm";
        elements.graphNodeTitle.textContent = `Node：${nodeId}`;
        elements.graphNodeMeta.textContent = `status：${nodeStatusLabel(nodeState.status)} ｜ execution_engine：${executionEngine}`;
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
        if (data.project_id && data.project_id !== state.projectId) {
          setProjectState(data.project_id);
          projectChanged = true;
        }
        if (data.chat_id) {
          state.chatId = data.chat_id;
        }
        if (projectChanged) {
          await loadProjects();
        }
      }

      async function confirmPlan(confirmed) {
        if (!state.plan) return;
        try {
          const path = state.plan.confirm_api || "/chat/plan/confirm";
          const payload =
            path === "/chat/plan/confirm"
              ? await apiFetch(path, {
                  method: "POST",
                  body: JSON.stringify({
                    project_id: state.projectId,
                    chat_id: state.chatId,
                    command: state.plan.command,
                    args: state.plan.args || {},
                    confirmed,
                  }),
                })
              : await apiFetch(path, {
                  method: "POST",
                  body: JSON.stringify({ ...state.plan.args, confirmed }),
                });
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
          if (path !== "/chat/plan/confirm") {
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

      async function loadRunArtifacts() {
        if (!state.projectId || !state.graphRunId) {
          state.runArtifacts = [];
          renderArtifactsInspector([]);
          return;
        }
        try {
          const payload = await apiFetch(`/runs/${encodeURIComponent(state.graphRunId)}/artifacts?project_id=${encodeURIComponent(state.projectId)}`);
          state.runArtifacts = payload.artifacts || [];
          renderArtifactsInspector(state.runArtifacts);
        } catch (error) {
          state.runArtifacts = [];
          renderArtifactsInspector([]);
          showToast(`載入 artifacts 失敗：${error.message}`, 9000, "danger");
        }
      }

      function renderArtifactsInspector(artifacts = []) {
        elements.artifactsInspectorList.innerHTML = "";
        if (!state.graphRunId) {
          elements.artifactsOverview.textContent = "尚未偵測到 Run，請先執行流程。";
          elements.artifactsEmpty.hidden = false;
          return;
        }
        elements.artifactsOverview.textContent = `Run ${shortenId(state.graphRunId)} 共 ${artifacts.length} 份產出物。`;
        if (!artifacts.length) {
          elements.artifactsEmpty.hidden = false;
          return;
        }
        elements.artifactsEmpty.hidden = true;

        artifacts.forEach((artifact) => {
          const card = document.createElement("article");
          card.className = "artifact-inspector-card";

          const header = document.createElement("header");
          const title = document.createElement("strong");
          title.textContent = artifact.name || artifact.path || "(未命名)";
          const meta = document.createElement("span");
          meta.textContent = `${formatFileSize(artifact.size)} · ${artifact.mime || "未知類型"}`;
          header.append(title, meta);
          card.appendChild(header);

          const path = document.createElement("p");
          path.className = "artifact-inspector-card__path";
          path.textContent = artifact.path || "";
          card.appendChild(path);

          if (isImageMime(artifact.mime)) {
            const preview = document.createElement("img");
            preview.className = "artifact-inspector-card__thumb";
            preview.src = artifact.url;
            preview.alt = `${artifact.name} 縮圖`;
            preview.loading = "lazy";
            card.appendChild(preview);
          }

          const actions = document.createElement("div");
          actions.className = "artifact-inspector-card__actions";
          const openBtn = document.createElement("button");
          openBtn.type = "button";
          openBtn.className = "secondary-btn small";
          openBtn.textContent = "預覽";
          openBtn.addEventListener("click", () => void openArtifactPreview(artifact));
          const downloadBtn = document.createElement("button");
          downloadBtn.type = "button";
          downloadBtn.className = "secondary-btn small";
          downloadBtn.textContent = "下載";
          downloadBtn.addEventListener("click", () => window.open(artifact.download_url, "_blank", "noopener"));
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
              await navigator.clipboard.writeText(text);
              showToast("已複製內容", 6000, "success");
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
        hint.addEventListener("click", () => switchContextTab("artifacts"));
        row.appendChild(hint);
        elements.timeline.appendChild(row);
      }

      function renderArtifacts(artifacts = []) {
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

      function applyTokenChunk(text = "") {
        if (!state.pendingAssistantBubble) {
          state.pendingAssistantBubble = appendMessage("agent", "Amon：", { status: "streaming" });
          state.pendingAssistantBubble.dataset.buffer = "";
        }
        state.pendingAssistantBubble.dataset.buffer = `${state.pendingAssistantBubble.dataset.buffer || ""}${text}`;
        state.pendingAssistantBubble.innerHTML = renderMarkdown(`Amon：${state.pendingAssistantBubble.dataset.buffer}`);
        elements.timeline.scrollTop = elements.timeline.scrollHeight;
      }

      function finalizeAssistantBubble() {
        state.pendingAssistantBubble = null;
      }

      function startStream(message, attachments = []) {
        resetPlanCard();
        const finalMessage = `${message}${buildAttachmentSummary(attachments)}`;
        appendMessage("user", `你：${finalMessage}`);
        appendTimelineStatus("訊息已送出，等待事件回傳中...");
        updateThinking({ status: "queued", brief: "已送出，等待伺服器事件" });
        updateExecutionStep("thinking", { title: "Thinking", status: "running", details: "訊息已送出，等待模型分析" });
        updateExecutionStep("planning", { title: "Planning", status: "pending", details: "尚未開始規劃" });
        updateExecutionStep("tool_execution", { title: "Tool execution", status: "pending", details: "等待工具呼叫" });
        updateExecutionStep("node_status", { title: "Node 狀態", status: "pending", details: "等待 run/node 事件", inferred: true });
        setStreaming(true);

        state.streamClient = new EventStreamClient({
          preferSSE: true,
          sseUrlBuilder: (params, lastEventId) => {
            const query = new URLSearchParams({ message: params.message });
            if (params.project_id) query.set("project_id", params.project_id);
            if (params.chat_id) query.set("chat_id", params.chat_id);
            if (lastEventId) query.set("last_event_id", lastEventId);
            return `/v1/chat/stream?${query.toString()}`;
          },
          wsUrlBuilder: (params, lastEventId) => {
            const protocol = window.location.protocol === "https:" ? "wss" : "ws";
            const query = new URLSearchParams({ message: params.message });
            if (params.project_id) query.set("project_id", params.project_id);
            if (params.chat_id) query.set("chat_id", params.chat_id);
            if (lastEventId) query.set("last_event_id", lastEventId);
            return `${protocol}://${window.location.host}/v1/chat/ws?${query.toString()}`;
          },
          onStatusChange: ({ status, transport }) => {
            if (status === "connected") {
              setStatusText(elements.shellDaemonStatus, "Daemon：Healthy", mapDaemonStatusLevel("connected"), "daemon 已連線");
            }
            if (status === "reconnecting") {
              setStatusText(elements.shellDaemonStatus, "Daemon：重新連線中", mapDaemonStatusLevel("reconnecting"), "daemon 連線中斷，正在重試");
              showToast(`串流中斷，正在重新連線（${formatUnknownValue(transport, "未知傳輸") }）`, 9000, "warning");
            }
            if (status === "error") {
              setStatusText(elements.shellDaemonStatus, "Daemon：Unavailable", mapDaemonStatusLevel("error"), "daemon 未連線或不可用");
            }
          },
          onEvent: async (eventType, data) => {
            try {
              state.uiStore.applyEvent(eventType, data);
              await applySessionFromEvent(data);
              if (state.projectId && ["result", "done", "notice"].includes(eventType)) {
                await loadContext();
              }
              applyExecutionEvent(eventType, data);
              if (eventType === "token") {
                applyTokenChunk(data.text || "");
                return;
              }
              if (eventType === "notice") {
                if (data.text) appendMessage("agent", data.text);
                return;
              }
              if (eventType === "plan") {
                showPlanCard(data);
                appendMessage("agent", "Amon：已產生 Plan Card，請確認。");
                return;
              }
              if (eventType === "result") {
                appendMessage("agent", `Amon：

\`\`\`json
${JSON.stringify(data, null, 2)}
\`\`\``);
                return;
              }
              if (eventType === "error") {
                showToast(data.message || "串流失敗", 9000, "danger");
                return;
              }
              if (eventType === "done") {
                await applySessionFromEvent(data);
                const doneStatus = data.status || "ok";
                if (doneStatus !== "ok" && doneStatus !== "confirm_required") {
                  appendMessage("agent", `Amon：流程結束（${doneStatus}）。我已收到你的訊息，請調整描述後再送出，我會持續回應。`);
                  appendTimelineStatus(`流程狀態：${doneStatus}`);
                }
                finalizeAssistantBubble();
                state.streamClient?.stop();
                state.streamClient = null;
                setStreaming(false);
                await loadProjects();
                if (state.projectId) {
                  await loadContext();
                  appendArtifactsHintToTimeline(state.runArtifacts.length);
                }
              }
            } catch (error) {
              console.error("stream_event_error", error);
              showToast(`事件處理失敗：${error.message || error}`);
            }
          },
        });

        state.streamClient.start({
          message: finalMessage,
          project_id: state.projectId,
          chat_id: state.chatId,
        });
      }

      function renderAttachmentPreview() {
        elements.attachmentPreview.innerHTML = "";
        if (!state.attachments || state.attachments.length === 0) return;
        state.attachments.forEach((file) => {
          const item = document.createElement("div");
          item.className = "attachment-item";
          const info = document.createElement("div");
          info.className = "attachment-info";
          info.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
          if (file.type.startsWith("image/")) {
            const img = document.createElement("img");
            img.alt = file.name;
            img.src = URL.createObjectURL(file);
            img.onload = () => URL.revokeObjectURL(img.src);
            item.appendChild(img);
          } else if (file.type.startsWith("video/")) {
            const video = document.createElement("video");
            video.src = URL.createObjectURL(file);
            video.controls = true;
            video.onloadeddata = () => URL.revokeObjectURL(video.src);
            item.appendChild(video);
          } else if (file.type === "application/pdf") {
            const embed = document.createElement("embed");
            embed.src = URL.createObjectURL(file);
            embed.type = "application/pdf";
            embed.onload = () => URL.revokeObjectURL(embed.src);
            item.appendChild(embed);
          }
          item.appendChild(info);
          elements.attachmentPreview.appendChild(item);
        });
      }

      elements.shellNavItems.forEach((link) => {
        link.addEventListener("click", (event) => {
          const routeKey = link.dataset.route || "chat";
          if (window.location.hash === `#/${routeKey}`) {
            event.preventDefault();
            void applyRoute(routeKey);
          }
        });
      });

      window.addEventListener("hashchange", () => {
        const routeKey = resolveRouteFromHash();
        void applyRoute(routeKey);
      });

      elements.logsRefresh.addEventListener("click", () => loadLogsPage(1));
      elements.eventsRefresh.addEventListener("click", () => loadEventsPage(1));
      elements.logsPrev.addEventListener("click", () => loadLogsPage(Math.max(1, state.logsPage.logsPage - 1)));
      elements.logsNext.addEventListener("click", () => {
        if (state.logsPage.logsHasNext) {
          loadLogsPage(state.logsPage.logsPage + 1);
        }
      });
      elements.eventsPrev.addEventListener("click", () => loadEventsPage(Math.max(1, state.logsPage.eventsPage - 1)));
      elements.eventsNext.addEventListener("click", () => {
        if (state.logsPage.eventsHasNext) {
          loadEventsPage(state.logsPage.eventsPage + 1);
        }
      });
      elements.logsDownload.addEventListener("click", () => {
        const url = `/v1/logs/download?${buildLogsQuery(1).toString()}`;
        window.open(url, "_blank", "noopener");
      });

      elements.toolsSkillsRefresh.addEventListener("click", loadToolsSkillsPage);
      elements.docsRefresh.addEventListener("click", loadDocsPage);
      elements.docsTreeViewport.addEventListener("scroll", renderDocsVirtualList);
      elements.docsFilter?.addEventListener("input", async (event) => {
        state.docsFilterQuery = event.target.value || "";
        renderDocs(state.docsItems || []);
        elements.docsTreeMeta.textContent = `共 ${state.docsFilteredItems.length} / ${state.docsItems.length} 份文件（虛擬列表）`;
        if (!state.docsFilteredItems.find((doc) => doc.path === state.docsSelectedPath)) {
          state.docsSelectedPath = state.docsFilteredItems[0]?.path || null;
        }
        renderDocsVirtualList();
        if (state.docsSelectedPath) {
          await selectDoc(state.docsSelectedPath);
        }
      });
      elements.docsOpen.addEventListener("click", () => {
        const selected = getSelectedDoc();
        if (!selected || !state.projectId) return;
        window.open(`/v1/projects/${encodeURIComponent(state.projectId)}/docs/content?path=${encodeURIComponent(selected.path)}`, "_blank", "noopener");
      });
      elements.docsDownload.addEventListener("click", () => {
        const selected = getSelectedDoc();
        if (!selected || !state.projectId) return;
        window.open(`/v1/projects/${encodeURIComponent(state.projectId)}/docs/download?path=${encodeURIComponent(selected.path)}`, "_blank", "noopener");
      });
      elements.docsInsert.addEventListener("click", () => {
        const selected = getSelectedDoc();
        if (!selected) return;
        const docRef = ` @doc(${selected.path})`;
        elements.chatInput.value = `${elements.chatInput.value}${docRef}`.trim();
        elements.chatInput.focus();
        showToast("已插入 @doc 引用。");
      });
      elements.configRefresh.addEventListener("click", loadConfigPage);
      elements.billRefresh.addEventListener("click", loadBillPage);
      elements.configSearch.addEventListener("input", renderConfigTable);
      elements.configExport.addEventListener("click", exportEffectiveConfig);
      elements.skillTriggerPreview.addEventListener("click", async () => {
        const skillName = elements.skillTriggerSelect.value;
        if (!skillName) {
          showToast("請先選擇 skill。");
          return;
        }
        try {
          const payload = await apiFetch("/skills/trigger-preview", {
            method: "POST",
            body: JSON.stringify({ skill_name: skillName, project_id: state.projectId || "" }),
          });
          elements.skillInjectionPreview.textContent = JSON.stringify(payload, null, 2);
          showToast("已產生 skill 注入預覽。");
        } catch (error) {
          showToast(`技能預覽失敗：${error.message}`);
        }
      });

      elements.chatForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const message = elements.chatInput.value.trim();
        if (!message) return;
        const attachments = [...state.attachments];
        elements.chatInput.value = "";
        elements.chatAttachments.value = "";
        state.attachments = [];
        renderAttachmentPreview();
        startStream(message, attachments);
      });

      elements.projectSelect.addEventListener("change", async (event) => {
        const selectedProject = event.target.value;
        setProjectState(selectedProject);
        await loadProjectHistory();
        if (state.projectId) {
          await ensureChatSession();
          await loadContext();
        }
        await loadShellViewDependencies(state.shellView);
      });

      elements.refreshContext.addEventListener("click", loadContext);
      elements.planConfirm.addEventListener("click", () => confirmPlan(true));
      elements.planCancel.addEventListener("click", () => confirmPlan(false));
      elements.graphNodeClose.addEventListener("click", closeNodeDrawer);
      elements.graphCreateTemplate.addEventListener("click", () => {
        if (!state.projectId || !state.graphRunId) {
          showToast("需要先有 run 才能建立 template。");
          return;
        }
        queuePlanCommand(
          "graph.template.create",
          { project_id: state.projectId, run_id: state.graphRunId, name: `${state.projectId}-${state.graphRunId}` },
          "建立 graph template（需確認）"
        );
      });
      elements.graphParametrize.addEventListener("click", () => {
        if (!state.graphTemplateId) {
          showToast("請先 Create template。\n此操作需要 Plan Card。");
          return;
        }
        if (!state.graphSelectedNodeId) {
          showToast("請先選擇 node。");
          return;
        }
        const varName = window.prompt("請輸入變數名稱（例如 customer_name）", "var");
        if (!varName) return;
        const jsonPath = window.prompt("請輸入 JSONPath（例如 $.nodes[0].args.prompt）", "");
        if (!jsonPath) return;
        queuePlanCommand(
          "graph.template.parametrize",
          { template_id: state.graphTemplateId, jsonpath: jsonPath, var_name: varName },
          `參數化 template（需確認）\nnode: ${state.graphSelectedNodeId}`
        );
      });
      elements.chatAttachments.addEventListener("change", (event) => {
        state.attachments = Array.from(event.target.files || []);
        renderAttachmentPreview();
      });
      elements.contextTabs.forEach((tab) => {
        tab.addEventListener("click", () => {
          switchContextTab(tab.dataset.contextTab);
          if (tab.dataset.contextTab === "artifacts") {
            void loadRunArtifacts();
          }
        });
      });

      elements.artifactsGoRun?.addEventListener("click", () => switchContextTab("run"));
      elements.artifactsGoLogs?.addEventListener("click", () => switchContextTab("logs"));
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
        try {
          await navigator.clipboard.writeText(runId);
          showToast("已複製完整 Run ID。", 7000, "success");
        } catch (error) {
          showToast(`複製失敗：${error.message || error}`, 9000, "danger");
        }
      });

      elements.contextSaveDraft?.addEventListener("click", saveContextDraft);
      elements.contextImportFile?.addEventListener("change", (event) => {
        const file = event.target.files?.[0];
        importContextDraftFromFile(file);
        event.target.value = "";
      });
      elements.contextExtractChat?.addEventListener("click", extractContextFromChat);
      elements.contextClearChat?.addEventListener("click", () => void clearContextDraft("chat"));
      elements.contextClearProject?.addEventListener("click", () => void clearContextDraft("project"));

      elements.thinkingMode.addEventListener("change", (event) => {
        state.thinkingMode = event.target.value;
        updateThinking({ status: "idle", brief: "已切換 Thinking 顯示模式" });
      });

      (async () => {
        try {
          await loadProjects();
          setProjectState(state.projectId);
          renderArtifacts([]);
          updateThinking({ status: "idle", brief: "目前沒有 Thinking 事件" });
          await loadProjectHistory();
          if (state.projectId) {
            await ensureChatSession();
            await loadContext();
          }
          const routeKey = resolveRouteFromHash();
          if (!window.location.hash) {
            navigateToRoute(routeKey);
          } else {
            await applyRoute(routeKey);
          }
        } catch (error) {
          showToast(`初始化失敗：${error.message}`);
        }
      })();

window.addEventListener("error", (event) => {
  console.error("ui_global_error", event.error || event.message);
});

window.addEventListener("unhandledrejection", (event) => {
  console.error("ui_unhandled_rejection", event.reason);
});
