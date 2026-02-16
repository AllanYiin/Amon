function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || "";
}

function formatMetric(cost, usage, currency) {
  return `${currency} ${Number(cost || 0).toFixed(2)} / ${Number(usage || 0).toFixed(2)}`;
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
    const fields = {
      today: rootEl.querySelector("#bill-today"),
      total: rootEl.querySelector("#bill-project-total"),
      mode: rootEl.querySelector("#bill-mode-summary"),
      run: rootEl.querySelector("#bill-current-run"),
    };

    const local = { chart: null };

    function render(summary, series = []) {
      const currency = summary?.currency || "USD";
      fields.today.textContent = formatMetric(summary?.today?.cost, summary?.today?.usage, currency);
      fields.total.textContent = formatMetric(summary?.project_total?.cost, summary?.project_total?.usage, currency);
      fields.mode.textContent = `automation ${formatMetric(summary?.mode_breakdown?.automation?.cost, summary?.mode_breakdown?.automation?.usage, currency)}｜interactive ${formatMetric(summary?.mode_breakdown?.interactive?.cost, summary?.mode_breakdown?.interactive?.usage, currency)}`;
      fields.run.textContent = formatMetric(summary?.current_run?.cost, summary?.current_run?.usage, currency);

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
            }],
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

    this.__billingCleanup = () => {
      refreshBtn?.removeEventListener("click", onRefresh);
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
