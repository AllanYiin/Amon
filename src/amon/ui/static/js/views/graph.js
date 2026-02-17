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
      (graph?.nodes || []).forEach((node) => {
        const li = document.createElement("li");
        li.className = "graph-node-item";
        li.innerHTML = `<button type="button" class="graph-node-item__button" data-node-id="${node.id}">${node.id}</button>`;
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
        previewEl.innerHTML = '<p class="empty-context">此 Run 尚無流程圖資料。</p>';
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

      local.runId = ctx.appState?.graphRunId || runs[0]?.id || runs[0]?.run_id || "";
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
