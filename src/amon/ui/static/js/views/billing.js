function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || "";
}

function metricValue(cost, usage, currency) {
  const hasCost = Number.isFinite(Number(cost));
  const hasUsage = Number.isFinite(Number(usage));
  if (!hasCost && !hasUsage) return "--";
  const amount = hasCost ? `${currency} ${Number(cost).toFixed(2)}` : "--";
  const usageText = hasUsage ? Number(usage).toLocaleString("zh-TW", { maximumFractionDigits: 2 }) : "--";
  return `${amount} / ${usageText}`;
}

function modelRate(model) {
  const usage = Number(model?.usage || 0);
  const cost = Number(model?.cost || 0);
  if (!usage || !cost) return "--";
  return (cost / usage * 1000).toFixed(4);
}

function toEntries(payload) {
  return Object.entries(payload || {}).sort((a, b) => Number(b[1]?.cost || 0) - Number(a[1]?.cost || 0));
}

function emptyBlock(message) {
  const el = document.createElement("div");
  el.className = "bill-empty";
  el.textContent = message;
  return el;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

/** @type {import('./contracts.js').ViewContract} */
export const BILLING_VIEW = {
  id: "bill",
  route: "/billing",
  mount: (ctx) => {
    const rootEl = ctx.rootEl;
    if (!rootEl) return;
    const chartEl = rootEl.querySelector("#bill-run-chart");
    const refreshBtn = rootEl.querySelector("#bill-refresh");
    const rangeBtns = ["#bill-range-7d", "#bill-range-30d", "#bill-range-all"].map((selector) => rootEl.querySelector(selector)).filter(Boolean);
    const fields = {
      today: rootEl.querySelector("#bill-today"),
      total: rootEl.querySelector("#bill-project-total"),
      mode: rootEl.querySelector("#bill-mode-summary"),
      run: rootEl.querySelector("#bill-current-run"),
      budgets: rootEl.querySelector("#bill-budgets"),
      exceeded: rootEl.querySelector("#bill-exceeded"),
      model: rootEl.querySelector("#bill-breakdown-model"),
      provider: rootEl.querySelector("#bill-breakdown-provider"),
      agent: rootEl.querySelector("#bill-breakdown-agent"),
      node: rootEl.querySelector("#bill-breakdown-node"),
      sessions: rootEl.querySelector("#bill-recent-sessions"),
      rawJson: rootEl.querySelector("#bill-raw-json"),
    };

    const local = { chart: null };

    function renderRows(container, payload = {}, currency = "USD") {
      if (!container) return;
      container.innerHTML = "";
      const entries = toEntries(payload);
      if (!entries.length) {
        container.appendChild(emptyBlock("尚無資料。"));
        return;
      }
      entries.forEach(([key, value]) => {
        const row = document.createElement("article");
        row.className = "bill-row";
        row.innerHTML = `
          <div>
            <strong>${escapeHtml(key)}</strong>
            <div class="bill-row__meta">records ${Number(value?.records || 0).toLocaleString("zh-TW")}</div>
          </div>
          <div class="bill-row__value">
            <strong>${metricValue(value?.cost, value?.usage, currency)}</strong>
          </div>
        `;
        container.appendChild(row);
      });
    }

    function renderBudgets(payload = {}, currency = "USD") {
      if (!fields.budgets) return;
      fields.budgets.innerHTML = "";
      const entries = Object.entries(payload || {});
      if (!entries.length) {
        fields.budgets.appendChild(emptyBlock("尚未設定 budgets。"));
        return;
      }
      entries.forEach(([name, value]) => {
        const row = document.createElement("article");
        row.className = "bill-row";
        const limit = Number(value?.limit ?? value?.amount);
        const spent = Number(value?.spent ?? value?.cost);
        const usage = Number(value?.usage);
        const metric = Number.isFinite(spent) || Number.isFinite(usage)
          ? metricValue(spent, usage, currency)
          : JSON.stringify(value || {});
        row.innerHTML = `
          <div>
            <strong>${escapeHtml(name)}</strong>
            <div class="bill-row__meta">limit ${Number.isFinite(limit) ? `${currency} ${limit.toFixed(2)}` : "--"}</div>
          </div>
          <div class="bill-row__value">
            <strong>${escapeHtml(metric)}</strong>
          </div>
        `;
        fields.budgets.appendChild(row);
      });
    }

    function renderModelCards(payload = {}, currency = "USD") {
      if (!fields.model) return;
      fields.model.innerHTML = "";
      const entries = toEntries(payload);
      if (!entries.length) {
        fields.model.appendChild(emptyBlock("尚無 model breakdown。"));
        return;
      }
      entries.forEach(([modelName, value]) => {
        const card = document.createElement("article");
        card.className = "bill-model-card";
        card.innerHTML = `
          <div class="bill-model-card__title">
            <span>${escapeHtml(modelName)}</span>
            <span class="pill pill--neutral">${Number(value?.records || 0)} sessions</span>
          </div>
          <div class="bill-model-card__meta">
            <div><span>Spend</span><strong>${Number(value?.cost || 0).toFixed(2)} ${currency}</strong></div>
            <div><span>Usage</span><strong>${Number(value?.usage || 0).toLocaleString("zh-TW", { maximumFractionDigits: 2 })}</strong></div>
            <div><span>Rate / 1k</span><strong>${modelRate(value)}</strong></div>
            <div><span>Records</span><strong>${Number(value?.records || 0).toLocaleString("zh-TW")}</strong></div>
          </div>
        `;
        fields.model.appendChild(card);
      });
    }

    function renderSessions(series = [], currency = "USD") {
      if (!fields.sessions) return;
      fields.sessions.innerHTML = "";
      if (!series.length) {
        fields.sessions.appendChild(emptyBlock("目前沒有可顯示的 sessions。"));
        return;
      }
      series.slice(-5).reverse().forEach((item) => {
        const row = document.createElement("article");
        row.className = "bill-row";
        const runId = item.run_id || item.runId || "(unknown)";
        row.innerHTML = `
          <div>
            <strong>${escapeHtml(runId)}</strong>
            <div class="bill-row__meta">Run history</div>
          </div>
          <div class="bill-row__value">
            <strong>${Number(item.cost || 0).toFixed(2)} ${currency}</strong>
          </div>
        `;
        fields.sessions.appendChild(row);
      });
    }

    function renderExceeded(events = []) {
      if (!fields.exceeded) return;
      fields.exceeded.innerHTML = "";
      if (!events.length) {
        fields.exceeded.appendChild(emptyBlock("目前沒有超限事件。"));
        return;
      }
      events.forEach((event) => {
        const item = document.createElement("li");
        item.className = "bill-row";
        item.innerHTML = `
          <div>
            <strong>budget_exceeded</strong>
            <div class="bill-row__meta">${escapeHtml(event.ts || "-")}</div>
          </div>
          <div class="bill-row__value">
            <strong>${escapeHtml(event.budget_name || event.scope || "-")}</strong>
          </div>
        `;
        fields.exceeded.appendChild(item);
      });
    }

    function render(summary, series = []) {
      const currency = summary?.currency || "USD";
      fields.today.textContent = metricValue(summary?.today?.cost, summary?.today?.usage, currency);
      fields.total.textContent = metricValue(summary?.project_total?.cost, summary?.project_total?.usage, currency);
      fields.mode.textContent = [
        `automation ${metricValue(summary?.mode_breakdown?.automation?.cost, summary?.mode_breakdown?.automation?.usage, currency)}`,
        `interactive ${metricValue(summary?.mode_breakdown?.interactive?.cost, summary?.mode_breakdown?.interactive?.usage, currency)}`,
      ].join("｜");
      fields.run.textContent = metricValue(summary?.current_run?.cost, summary?.current_run?.usage, currency);

      renderBudgets(summary?.budgets || {}, currency);
      renderRows(fields.provider, summary?.breakdown?.provider || {}, currency);
      renderRows(fields.agent, summary?.breakdown?.agent || {}, currency);
      renderRows(fields.node, summary?.breakdown?.node || {}, currency);
      renderModelCards(summary?.breakdown?.model || {}, currency);
      renderExceeded(summary?.exceeded_events || []);
      renderSessions(series, currency);
      if (fields.rawJson) {
        fields.rawJson.textContent = JSON.stringify({ summary, series }, null, 2);
      }

      if (local.chart) {
        local.chart.destroy();
        local.chart = null;
      }
      if (window.Chart && chartEl && series.length) {
        local.chart = new window.Chart(chartEl.getContext("2d"), {
          type: "bar",
          data: {
            labels: series.map((item) => item.run_id || item.runId || "-"),
            datasets: [{
              label: `每 Run 花費（${currency}）`,
              data: series.map((item) => Number(item.cost || 0)),
              backgroundColor: "rgba(37, 99, 235, 0.5)",
              borderColor: "rgba(59, 130, 246, 1)",
              borderWidth: 1,
              borderRadius: 6,
            }],
          },
          options: {
            maintainAspectRatio: false,
            responsive: true,
            scales: { y: { beginAtZero: true } },
          },
        });
      }
    }

    async function load() {
      try {
        const projectId = getProjectId(ctx);
        const [summary, series] = await Promise.all([
          ctx.services.billing.getBillingSummary(projectId),
          ctx.services.billing.getBillingSeries(projectId),
        ]);
        ctx.store?.dispatch?.({ type: "@@store/patch", payload: { billingView: { summary, series } } });
        render(summary, series);
      } catch (error) {
        ctx.ui.toast?.show(`載入 Billing 失敗：${error.message}`, { type: "danger", duration: 12000 });
      }
    }

    const onRefresh = () => void load();
    refreshBtn?.addEventListener("click", onRefresh);

    const onRangeClick = (currentButton) => {
      rangeBtns.forEach((button) => {
        const isActive = button === currentButton;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
      });
    };
    const rangeHandlers = new Map();
    rangeBtns.forEach((button) => {
      const handler = () => onRangeClick(button);
      rangeHandlers.set(button, handler);
      button.addEventListener("click", handler);
    });

    this.__billingCleanup = () => {
      refreshBtn?.removeEventListener("click", onRefresh);
      rangeHandlers.forEach((handler, button) => {
        button.removeEventListener("click", handler);
      });
      if (local.chart) {
        local.chart.destroy();
        local.chart = null;
      }
    };
    this.__billingLoad = load;
  },
  unmount() {
    this.__billingCleanup?.();
    this.__billingCleanup = null;
    this.__billingLoad = null;
  },
  onRoute: async () => {
    await BILLING_VIEW.__billingLoad?.();
  },
};
