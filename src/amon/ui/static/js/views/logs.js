function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || "";
}

function esc(v) {
  return String(v || "").replace(/[&<>"']/g, (s) => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[s]));
}

/** @type {import('./contracts.js').ViewContract} */
export const LOGS_VIEW = {
  id: "logs-events",
  route: "/logs",
  mount: (ctx) => {
    const rootEl = ctx.rootEl;
    if (!rootEl) return;
    const listEl = rootEl.querySelector("#logs-list");
    const summaryEl = rootEl.querySelector("#logs-summary");
    const refreshBtn = rootEl.querySelector("#logs-refresh");
    const runInput = rootEl.querySelector("#logs-filter-run");

    const controller = { current: null };

    function renderLoading() {
      summaryEl.textContent = "載入中...";
      listEl.innerHTML = '<p class="empty-context">正在查詢 logs。</p>';
    }

    function renderError(message) {
      summaryEl.textContent = "載入失敗";
      listEl.innerHTML = `<p class="empty-context">${esc(message)}</p>`;
    }

    function renderLogs(payload = {}) {
      const items = payload.items || payload.logs || [];
      summaryEl.textContent = `共 ${payload.total || items.length} 筆`;
      listEl.innerHTML = "";
      items.forEach((item) => {
        const card = document.createElement("article");
        card.className = "log-item";
        card.innerHTML = `<header><strong>${esc(item.level || item.severity || 'INFO')}</strong> · <code>${esc(item.ts || '-')}</code></header><pre>${esc(JSON.stringify(item, null, 2))}</pre>`;
        listEl.appendChild(card);
      });
      if (!items.length) {
        listEl.innerHTML = '<p class="empty-context">查無資料</p>';
      }
    }

    async function load() {
      controller.current?.abort();
      controller.current = new AbortController();
      renderLoading();
      try {
        const payload = await ctx.services.logs.getLogs(runInput?.value || "", getProjectId(ctx));
        ctx.store?.dispatch?.({ type: "@@store/patch", payload: { logsView: payload } });
        renderLogs(payload);
      } catch (error) {
        if (error.name === "AbortError") return;
        renderError(error.message);
      }
    }

    const onRefresh = () => void load();
    refreshBtn?.addEventListener("click", onRefresh);

    this.__logsCleanup = () => {
      refreshBtn?.removeEventListener("click", onRefresh);
      controller.current?.abort();
    };
    this.__logsLoad = load;
  },
  unmount() {
    this.__logsCleanup?.();
    this.__logsCleanup = null;
    this.__logsLoad = null;
  },
  onRoute: async () => {
    await LOGS_VIEW.__logsLoad?.();
  },
};
