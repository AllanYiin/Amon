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

    const local = { graph: null, panZoom: null };

    async function renderGraph(graph) {
      local.graph = graph || {};
      codeEl.textContent = graph?.mermaid || "";
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

      if (graph?.mermaid && window.__mermaid) {
        const { svg } = await window.__mermaid.render(`graph-preview-${Date.now()}`, graph.mermaid);
        previewEl.innerHTML = svg;
        const svg = previewEl.querySelector("svg");
        if (svg && window.svgPanZoom) {
          local.panZoom = window.svgPanZoom(svg, { controlIconsEnabled: true, fit: true, center: true });
        }
      }
    }

    async function openNode(nodeId) {
      try {
        const runId = ctx.appState?.graphRunId;
        if (!runId) return;
        const detail = await ctx.services.graph.getNodeDetail(runId, nodeId, getProjectId(ctx));
        ctx.store?.dispatch?.({ type: "@@store/patch", payload: { graphView: { selectedNode: detail } } });
      } catch (error) {
        ctx.ui.toast?.show(`讀取節點失敗：${error.message}`, { type: "danger", duration: 12000 });
      }
    }

    async function load() {
      const runId = ctx.appState?.graphRunId;
      if (!runId) {
        runMetaEl.textContent = "尚未偵測到 Run";
        return;
      }
      runMetaEl.textContent = `Run: ${runId}`;
      try {
        const graph = await ctx.services.graph.getGraph(runId, getProjectId(ctx));
        ctx.store?.dispatch?.({ type: "@@store/patch", payload: { graphView: { graph, runId } } });
        await renderGraph(graph);
      } catch (error) {
        ctx.ui.toast?.show(`載入 Graph 失敗：${error.message}`, { type: "danger", duration: 12000 });
      }
    }

    const onListClick = (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const node = target.closest("[data-node-id]");
      if (!node) return;
      void openNode(node.dataset.nodeId || "");
    };

    listEl.addEventListener("click", onListClick);

    this.__graphCleanup = () => {
      listEl.removeEventListener("click", onListClick);
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
