import { logViewInitDebug } from "../utils/debug.js";

function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || "";
}

/** @type {import('./contracts.js').ViewContract} */
export const GRAPH_VIEW = {
  id: "graph",
  route: "/graph",
  mount: (ctx) => {
    const rootEl = ctx.rootEl;
    if (!rootEl) return;
    logViewInitDebug("graph", {
      project_id: ctx.appState?.projectId || getProjectId(ctx) || null,
      run_id: ctx.appState?.graphRunId || null,
      chat_id: ctx.appState?.chatId || null,
      node_states_count: Object.keys(ctx.appState?.graphNodeStates || {}).length,
    });

    const previewEl = rootEl.querySelector("#graph-preview");
    const listEl = rootEl.querySelector("#graph-node-list");
    const codeEl = rootEl.querySelector("#graph-code");
    const runMetaEl = rootEl.querySelector("#graph-run-meta");
    const runSelectEl = rootEl.querySelector("#graph-run-select");
    const refreshEl = rootEl.querySelector("#graph-history-refresh");
    const copyRunIdEl = ctx.elements?.copyRunId;

    const local = { graph: null, panZoom: null, runId: "" };

    async function renderGraph(payload) {
      const graph = payload?.graph || {};
      local.graph = graph;
      codeEl.textContent = payload?.graph_mermaid || "";
      listEl.innerHTML = "";
      const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
      if (!nodes.length) {
        listEl.innerHTML = '<li><p class="graph-empty-state">目前沒有可顯示的節點資料。</p></li>';
      }
      nodes.forEach((node) => {
        const rawStatus = String(node?.status || node?.state || "pending").toLowerCase();
        const normalizedStatus = ["running", "succeeded", "failed"].includes(rawStatus) ? rawStatus : "pending";
        const progressValue = Number.isFinite(Number(node?.progress)) ? Math.max(0, Math.min(100, Number(node.progress))) : null;
        const progressMeta = progressValue === null ? "" : `<span>${Math.round(progressValue)}%</span>`;
        const progressBlock = progressValue === null
          ? ""
          : `<div class="graph-node-item__progress" aria-label="Node progress"><span style="--graph-progress:${progressValue}%;"></span></div>`;
        const li = document.createElement("li");
        li.className = "graph-node-item";
        li.innerHTML = `
          <button type="button" class="graph-node-item__button list-row" data-node-id="${node.id}">
            <span class="graph-node-item__content">
              <strong class="graph-node-item__title">${node.id || "(unknown node)"}</strong>
              <span class="graph-node-item__meta">${progressMeta}${progressBlock}</span>
            </span>
            <span class="node-status node-status--${normalizedStatus}">${normalizedStatus}</span>
          </button>
        `;
        listEl.appendChild(li);
      });

      previewEl.innerHTML = "";
      local.panZoom?.destroy?.();
      local.panZoom = null;

      if (payload?.graph_mermaid && window.__mermaid) {
        const { svg } = await window.__mermaid.render(`graph-preview-${Date.now()}`, payload.graph_mermaid);
        previewEl.innerHTML = svg;
        const svgEl = previewEl.querySelector("svg");
        if (svgEl && window.svgPanZoom) {
          local.panZoom = window.svgPanZoom(svgEl, { controlIconsEnabled: true, fit: true, center: true });
        }
      } else {
        previewEl.innerHTML = '<p class="graph-empty-state">此 Run 尚無流程圖資料。</p>';
      }
    }

    async function openNode(nodeId) {
      try {
        if (!local.runId) return;
        const detail = await ctx.services.graph.getNodeDetail(local.runId, nodeId, getProjectId(ctx));
        ctx.store?.dispatch?.({ type: "@@store/patch", payload: { graphView: { selectedNode: detail } } });
      } catch (error) {
        ctx.ui.toast?.show(`讀取節點失敗：${error.message}`, { type: "danger", duration: 12000 });
      }
    }

    async function loadRuns() {
      const projectId = getProjectId(ctx);
      const runs = await ctx.services.graph.listRuns(projectId);
      runSelectEl.innerHTML = "";
      if (!runs.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "尚無歷史 Run";
        runSelectEl.appendChild(option);
        runSelectEl.disabled = true;
        local.runId = "";
        runMetaEl.textContent = "尚未偵測到 Run";
        if (copyRunIdEl) {
          copyRunIdEl.disabled = true;
          copyRunIdEl.dataset.runId = "";
        }
        return;
      }

      runSelectEl.disabled = false;
      runs.forEach((run) => {
        const option = document.createElement("option");
        option.value = run.id || run.run_id || "";
        option.textContent = `${run.id || run.run_id || "(unknown)"}｜${run.status || run.run_status || "unknown"}`;
        runSelectEl.appendChild(option);
      });

      const preferredRunId = ctx.appState?.graphRunId || "";
      if (preferredRunId && !runs.some((run) => (run.id || run.run_id || "") === preferredRunId)) {
        const fallback = document.createElement("option");
        fallback.value = preferredRunId;
        fallback.textContent = `${preferredRunId}｜current`;
        runSelectEl.prepend(fallback);
      }

      local.runId = preferredRunId || runs[0]?.id || runs[0]?.run_id || "";
      runSelectEl.value = local.runId;
    }

    async function loadGraph(runId = "") {
      if (!runId) {
        previewEl.innerHTML = '<p class="empty-context">請先選擇 Run。</p>';
        codeEl.textContent = "";
        listEl.innerHTML = "";
        return;
      }
      local.runId = runId;
      try {
        const graphPayload = await ctx.services.graph.getGraph(runId, getProjectId(ctx));
        runMetaEl.textContent = `Run：${runId}（${graphPayload?.run_status || "unknown"}）`;
        if (copyRunIdEl) {
          copyRunIdEl.disabled = false;
          copyRunIdEl.dataset.runId = runId;
        }
        await renderGraph(graphPayload || {});
      } catch (error) {
        if (copyRunIdEl) {
          copyRunIdEl.disabled = true;
          copyRunIdEl.dataset.runId = "";
        }
        ctx.ui.toast?.show(`載入 Graph 失敗：${error.message}`, { type: "danger", duration: 12000 });
      }
    }

    async function load() {
      try {
        await loadRuns();
        await loadGraph(local.runId);
      } catch (error) {
        ctx.ui.toast?.show(`讀取歷史 Run 失敗：${error.message}`, { type: "danger", duration: 12000 });
      }
    }

    const onListClick = (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const node = target.closest("[data-node-id]");
      if (!node) return;
      void openNode(node.dataset.nodeId || "");
    };

    const onRunChange = () => {
      void loadGraph(runSelectEl.value);
    };

    listEl.addEventListener("click", onListClick);
    runSelectEl?.addEventListener("change", onRunChange);
    refreshEl?.addEventListener("click", () => void load());

    this.__graphCleanup = () => {
      listEl.removeEventListener("click", onListClick);
      runSelectEl?.removeEventListener("change", onRunChange);
      local.panZoom?.destroy?.();
      local.panZoom = null;
    };
    this.__graphLoad = load;
  },
  unmount() {
    this.__graphCleanup?.();
    this.__graphCleanup = null;
    this.__graphLoad = null;
  },
  onRoute: async () => {
    await GRAPH_VIEW.__graphLoad?.();
  },
};
