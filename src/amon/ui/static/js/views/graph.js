import { logUiDebug, logViewInitDebug } from "../utils/debug.js";
import { buildGraphRuntimeViewModel } from "../domain/graphRuntimeAdapter.js";
import { copyText } from "../utils/clipboard.js";
import { downloadTextFile } from "../utils/download.js";

function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || "";
}

function formatJson(value) {
  if (value === undefined) return "{}";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeXml(value) {
  return escapeHtml(value);
}

function createSvgElement(tagName, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tagName);
  Object.entries(attributes).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    element.setAttribute(key, String(value));
  });
  return element;
}

function formatNodeIndex(order) {
  return String(Number(order) + 1).padStart(2, "0");
}

function getNodeMetaTokens(nodeVm) {
  const tokens = [];
  if (nodeVm.id) tokens.push(nodeVm.id);
  if (nodeVm.typeLabel) tokens.push(nodeVm.typeLabel);
  if (nodeVm.executorLabel) tokens.push(nodeVm.executorLabel);
  return tokens;
}

function resolveEdgeTone(sourceNode, targetNode) {
  if (!sourceNode || !targetNode) return "idle";
  if (targetNode.isFailed || sourceNode.isFailed) return "failed";
  if (targetNode.isCurrent || sourceNode.isCurrent) return "active";
  if (targetNode.isNext || targetNode.isQueued) return "ready";
  if (sourceNode.isCompleted && targetNode.isCompleted) return "complete";
  return "idle";
}

function buildEdgePath(sourceBox, targetBox) {
  const startX = sourceBox.x + sourceBox.width;
  const startY = sourceBox.y + sourceBox.height / 2;
  const endX = targetBox.x;
  const endY = targetBox.y + targetBox.height / 2;
  const deltaX = Math.max(72, (endX - startX) * 0.5);
  return `M ${startX} ${startY} C ${startX + deltaX} ${startY}, ${endX - deltaX} ${endY}, ${endX} ${endY}`;
}

function buildEdgeLabelPosition(sourceBox, targetBox) {
  const startX = sourceBox.x + sourceBox.width;
  const startY = sourceBox.y + sourceBox.height / 2;
  const endX = targetBox.x;
  const endY = targetBox.y + targetBox.height / 2;
  return {
    x: startX + (endX - startX) * 0.5,
    y: startY + (endY - startY) * 0.5 - 8,
  };
}

function createGraphLayout(viewModel) {
  const nodes = Array.isArray(viewModel?.nodes) ? [...viewModel.nodes].sort((left, right) => left.order - right.order) : [];
  const edges = Array.isArray(viewModel?.edges) ? viewModel.edges : [];
  const nodeWidth = 272;
  const nodeHeight = 188;
  const columnGap = 320;
  const rowGap = 48;
  const paddingX = 48;
  const paddingY = 40;
  const levelOrder = [...new Set(nodes.map((node) => Number(node.level) || 0))].sort((left, right) => left - right);
  const rowIndexByNode = new Map();
  const layoutNodes = [];
  const columns = [];
  let maxBottom = 0;

  levelOrder.forEach((level, columnIndex) => {
    const columnNodes = nodes
      .filter((node) => Number(node.level) === level)
      .sort((left, right) => {
        const leftAverage = left.predecessorIds?.length
          ? left.predecessorIds.reduce((sum, nodeId) => sum + (rowIndexByNode.get(nodeId) ?? 0), 0) / left.predecessorIds.length
          : left.order;
        const rightAverage = right.predecessorIds?.length
          ? right.predecessorIds.reduce((sum, nodeId) => sum + (rowIndexByNode.get(nodeId) ?? 0), 0) / right.predecessorIds.length
          : right.order;
        if (leftAverage !== rightAverage) return leftAverage - rightAverage;
        return left.order - right.order;
      });
    const x = paddingX + columnIndex * columnGap;
    const columnTop = paddingY - 18;
    const columnHeight = Math.max(160, columnNodes.length * (nodeHeight + rowGap) - rowGap + 36);
    const label = columnNodes.length > 1 ? `Parallel ×${columnNodes.length}` : `Stage ${String(columnIndex + 1).padStart(2, "0")}`;
    columns.push({
      level,
      x: x - 14,
      y: columnTop,
      width: nodeWidth + 28,
      height: columnHeight,
      label,
      count: columnNodes.length,
    });
    columnNodes.forEach((nodeVm, rowIndex) => {
      rowIndexByNode.set(nodeVm.id, rowIndex);
      const y = paddingY + rowIndex * (nodeHeight + rowGap);
      maxBottom = Math.max(maxBottom, y + nodeHeight);
      layoutNodes.push({
        ...nodeVm,
        box: { x, y, width: nodeWidth, height: nodeHeight },
      });
    });
  });

  const nodeById = new Map(layoutNodes.map((node) => [node.id, node]));
  const layoutEdges = edges
    .map((edge) => {
      const sourceNode = nodeById.get(edge.from);
      const targetNode = nodeById.get(edge.to);
      if (!sourceNode || !targetNode) return null;
      return {
        ...edge,
        sourceNode,
        targetNode,
        tone: resolveEdgeTone(sourceNode, targetNode),
        path: buildEdgePath(sourceNode.box, targetNode.box),
        labelPosition: buildEdgeLabelPosition(sourceNode.box, targetNode.box),
      };
    })
    .filter(Boolean);

  const width = Math.max(720, paddingX * 2 + Math.max(0, levelOrder.length - 1) * columnGap + nodeWidth);
  const height = Math.max(320, maxBottom + paddingY);

  return {
    width,
    height,
    nodes: layoutNodes,
    edges: layoutEdges,
    columns,
  };
}

function buildGraphCanvasSvg(layoutModel) {
  if (!layoutModel) return "";
  const defs = `
    <defs>
      <marker id="graph-arrow-idle" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"></path>
      </marker>
      <marker id="graph-arrow-active" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#2563eb"></path>
      </marker>
      <marker id="graph-arrow-ready" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#d97706"></path>
      </marker>
      <marker id="graph-arrow-complete" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#059669"></path>
      </marker>
      <marker id="graph-arrow-failed" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#dc2626"></path>
      </marker>
    </defs>
  `;
  const columnMarkup = layoutModel.columns.map((column) => `
    <g>
      <rect x="${column.x}" y="${column.y}" width="${column.width}" height="${column.height}" rx="26" fill="rgba(255,255,255,0.72)" stroke="rgba(148,163,184,0.28)" stroke-dasharray="${column.count > 1 ? "8 6" : "0"}"></rect>
      <text x="${column.x + 18}" y="${column.y + 28}" font-size="12" font-weight="700" fill="#64748b" letter-spacing="1.6">${escapeXml(column.label)}</text>
    </g>
  `).join("");

  const edgeColors = {
    idle: "#94a3b8",
    active: "#2563eb",
    ready: "#d97706",
    complete: "#059669",
    failed: "#dc2626",
  };

  const edgeMarkup = layoutModel.edges.map((edge) => {
    const color = edgeColors[edge.tone] || edgeColors.idle;
    const labelText = edge.label ? `
      <text x="${edge.labelPosition.x}" y="${edge.labelPosition.y}" font-size="11" font-weight="600" fill="${color}" text-anchor="middle">${escapeXml(edge.label)}</text>
    ` : "";
    return `
      <g>
        <path d="${edge.path}" fill="none" stroke="${color}" stroke-width="${edge.tone === "active" ? 3 : 2}" opacity="${edge.tone === "idle" ? "0.62" : "1"}" marker-end="url(#graph-arrow-${edge.tone})"></path>
        ${labelText}
      </g>
    `;
  }).join("");

  const nodeMarkup = layoutModel.nodes.map((node) => {
    const x = node.box.x;
    const y = node.box.y;
    const width = node.box.width;
    const height = node.box.height;
    const statusColors = {
      current: { fill: "#eff6ff", stroke: "#2563eb", text: "#1d4ed8" },
      next: { fill: "#fffbeb", stroke: "#d97706", text: "#b45309" },
      queued: { fill: "#fff7ed", stroke: "#fb923c", text: "#c2410c" },
      completed: { fill: "#ecfdf5", stroke: "#059669", text: "#047857" },
      failed: { fill: "#fef2f2", stroke: "#dc2626", text: "#b91c1c" },
      blocked: { fill: "#f8fafc", stroke: "#94a3b8", text: "#475569" },
      unknown: { fill: "#f8fafc", stroke: "#94a3b8", text: "#475569" },
      idle: { fill: "#ffffff", stroke: "#cbd5e1", text: "#475569" },
    };
    const palette = statusColors[node.flowRole] || statusColors.idle;
    const summary = node.displaySummary ? `<text x="${x + 20}" y="${y + 76}" font-size="12" fill="#475569">${escapeXml(node.displaySummary)}</text>` : "";
    const meta = getNodeMetaTokens(node).slice(0, 3).join(" · ");
    const progressMarkup = node.progress != null ? `
      <rect x="${x + 20}" y="${y + height - 28}" width="${width - 40}" height="6" rx="999" fill="rgba(148,163,184,0.2)"></rect>
      <rect x="${x + 20}" y="${y + height - 28}" width="${((width - 40) * node.progress) / 100}" height="6" rx="999" fill="#2563eb"></rect>
    ` : "";
    return `
      <g>
        <rect x="${x}" y="${y}" width="${width}" height="${height}" rx="24" fill="${palette.fill}" stroke="${palette.stroke}" stroke-width="${node.isCurrent || node.isNext ? 2.5 : 1.4}"></rect>
        <text x="${x + 20}" y="${y + 28}" font-size="11" font-weight="700" fill="#64748b">${escapeXml(formatNodeIndex(node.order))}</text>
        <text x="${x + 20}" y="${y + 52}" font-size="17" font-weight="700" fill="#0f172a">${escapeXml(node.displayTitle)}</text>
        ${summary}
        <text x="${x + 20}" y="${y + height - 52}" font-size="11" font-weight="600" fill="#64748b">${escapeXml(meta)}</text>
        <rect x="${x + 20}" y="${y + height - 46}" width="72" height="24" rx="999" fill="${palette.fill}" stroke="${palette.stroke}" stroke-width="1.2"></rect>
        <text x="${x + 56}" y="${y + height - 30}" font-size="11" font-weight="700" fill="${palette.text}" text-anchor="middle">${escapeXml(node.statusUi.label)}</text>
        ${progressMarkup}
      </g>
    `;
  }).join("");

  return `
    <svg xmlns="http://www.w3.org/2000/svg" width="${layoutModel.width}" height="${layoutModel.height}" viewBox="0 0 ${layoutModel.width} ${layoutModel.height}" role="img" aria-label="Amon execution flow">
      <rect width="100%" height="100%" rx="32" fill="#f8fafc"></rect>
      ${defs}
      ${columnMarkup}
      ${edgeMarkup}
      ${nodeMarkup}
    </svg>
  `.trim();
}

function buildNodeCardMarkup(nodeVm) {
  const progressMarkup = nodeVm.progress == null
    ? ""
    : `
      <div class="graph-flow-node__progress" aria-hidden="true">
        <span style="width:${Math.round(nodeVm.progress)}%"></span>
      </div>
    `;
  const summaryMarkup = nodeVm.displaySummary
    ? `<p class="graph-flow-node__summary">${escapeHtml(nodeVm.displaySummary)}</p>`
    : "";
  const metaMarkup = getNodeMetaTokens(nodeVm)
    .slice(0, 3)
    .map((token) => `<span class="graph-flow-node__meta-chip">${escapeHtml(token)}</span>`)
    .join("");
  return `
    <span class="graph-flow-node__chrome">
      <span class="graph-flow-node__head">
        <span class="graph-flow-node__icon material-symbols-rounded" aria-hidden="true">${escapeHtml(nodeVm.iconName || "account_tree")}</span>
        <span class="graph-flow-node__head-copy">
          <span class="graph-flow-node__order">STEP ${escapeHtml(formatNodeIndex(nodeVm.order))}</span>
          <strong class="graph-flow-node__title">${escapeHtml(nodeVm.displayTitle || nodeVm.id || "(unknown node)")}</strong>
        </span>
      </span>
      ${summaryMarkup}
      <span class="graph-flow-node__meta">${metaMarkup}</span>
      <span class="graph-flow-node__footer">
        <span class="node-status ${escapeHtml(nodeVm.statusUi.cssClass)}">${escapeHtml(nodeVm.statusUi.label)}</span>
        ${progressMarkup}
      </span>
    </span>
  `;
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
      thread_id: ctx.appState?.activeThreadId || null,
      node_states_count: Object.keys(ctx.appState?.graphNodeStates || {}).length,
    });

    const previewEl = rootEl.querySelector("#graph-preview");
    const listEl = rootEl.querySelector("#graph-node-list");
    const codeEl = rootEl.querySelector("#graph-code");
    const runMetaEl = rootEl.querySelector("#graph-run-meta");
    const runSelectEl = rootEl.querySelector("#graph-run-select");
    const refreshEl = rootEl.querySelector("#graph-history-refresh");
    const copyGraphEl = rootEl.querySelector("#graph-copy-mermaid");
    const exportSvgEl = rootEl.querySelector("#graph-export-svg");
    const copyRunIdEl = ctx.elements?.copyRunId;
    const drawerEl = ctx.elements?.graphNodeDrawer;
    const drawerCloseEl = ctx.elements?.graphNodeClose;
    const drawerTitleEl = ctx.elements?.graphNodeTitle;
    const drawerMetaEl = ctx.elements?.graphNodeMeta;
    const drawerInputsEl = ctx.elements?.graphNodeInputs;
    const drawerOutputsEl = ctx.elements?.graphNodeOutputs;
    const drawerEventsEl = ctx.elements?.graphNodeEvents;

    const local = {
      runId: "",
      viewModel: null,
      selectedNodeId: "",
      autoFocusNodeId: "",
      nodeDetails: new Map(),
      layoutModel: null,
      exportableSvg: "",
      canvasNodeEls: new Map(),
      listNodeEls: new Map(),
      unsubscribeLiveUpdates: null,
      refreshTimer: null,
      pendingRefreshKind: null,
      refreshInFlight: false,
    };

    const REFRESH_THROTTLE_MS = 450;

    function closeGraphNodeDrawer() {
      if (!drawerEl) return;
      drawerEl.hidden = true;
    }

    function openGraphNodeDrawer() {
      if (!drawerEl) return;
      drawerEl.hidden = false;
    }

    function renderGraphNodeDrawer(nodeDetail = null) {
      if (!drawerTitleEl || !drawerMetaEl || !drawerInputsEl || !drawerOutputsEl || !drawerEventsEl) return;
      if (!nodeDetail) {
        drawerTitleEl.textContent = "Node 詳細";
        drawerMetaEl.textContent = "尚未選擇節點";
        drawerInputsEl.textContent = "{}";
        drawerOutputsEl.textContent = "{}";
        drawerEventsEl.innerHTML = "<li>尚無 events/logs</li>";
        return;
      }

      const nodeId = nodeDetail.node_id || nodeDetail?.node?.id || local.selectedNodeId || "(unknown node)";
      const vmNode = local.viewModel?.nodes?.find((item) => item.id === nodeId);
      const statusLabel = vmNode?.statusUi?.label || "未知";
      const statusSource = vmNode?.statusSource || "fallback";
      const statePayload = nodeDetail.state && typeof nodeDetail.state === "object" ? nodeDetail.state : {};
      const outputPayload = statePayload.output ?? nodeDetail.output ?? {};
      const inputPayload = nodeDetail.node && typeof nodeDetail.node === "object"
        ? {
          args: nodeDetail.node.args,
          input: nodeDetail.node.input,
          inputs: nodeDetail.node.inputs,
          prompt: nodeDetail.node.prompt,
          content: nodeDetail.node.content,
          tool: nodeDetail.node.tool,
        }
        : {};

      drawerTitleEl.textContent = `Node：${nodeId}`;
      drawerMetaEl.textContent = `status：${statusLabel}（source: ${statusSource}）`;
      drawerInputsEl.textContent = formatJson(inputPayload);
      drawerOutputsEl.textContent = formatJson(outputPayload);
      drawerEventsEl.innerHTML = "";
      const events = Array.isArray(nodeDetail.events) ? nodeDetail.events : [];
      if (!events.length) {
        drawerEventsEl.innerHTML = "<li>尚無 events/logs</li>";
      } else {
        events.slice(-12).forEach((eventItem) => {
          const li = document.createElement("li");
          li.textContent = formatJson(eventItem);
          drawerEventsEl.appendChild(li);
        });
      }
    }

    function updateSelectedState() {
      local.listNodeEls.forEach((buttonEl, nodeId) => {
        const isSelected = nodeId === local.selectedNodeId;
        const isAutoFocus = nodeId === local.autoFocusNodeId;
        buttonEl.classList.toggle("is-selected", isSelected);
        buttonEl.classList.toggle("is-auto-focus", isAutoFocus);
        buttonEl.setAttribute("aria-pressed", isSelected ? "true" : "false");
      });
      local.canvasNodeEls.forEach((buttonEl, nodeId) => {
        const isSelected = nodeId === local.selectedNodeId;
        const isAutoFocus = nodeId === local.autoFocusNodeId;
        buttonEl.classList.toggle("is-selected", isSelected);
        buttonEl.classList.toggle("is-auto-focus", isAutoFocus);
        buttonEl.setAttribute("aria-pressed", isSelected ? "true" : "false");
        buttonEl.setAttribute("aria-current", isAutoFocus ? "step" : "false");
      });
    }

    async function selectNode(nodeId, options = {}) {
      const { forceRefresh = false, openDrawer = true } = options;
      const normalizedNodeId = String(nodeId || "").trim();
      if (!normalizedNodeId || !local.runId) return;
      local.selectedNodeId = normalizedNodeId;
      updateSelectedState();
      const cacheKey = `${local.runId}::${normalizedNodeId}`;
      try {
        let detail = local.nodeDetails.get(cacheKey);
        if (!detail || forceRefresh) {
          detail = await ctx.services.graph.getNodeDetail(local.runId, normalizedNodeId, getProjectId(ctx));
          local.nodeDetails.set(cacheKey, detail);
        }
        ctx.store?.dispatch?.({
          type: "@@store/patch",
          payload: { graphView: { selectedNodeId: normalizedNodeId, selectedNode: detail } },
        });
        renderGraphNodeDrawer(detail);
        if (openDrawer) openGraphNodeDrawer();
      } catch (error) {
        ctx.ui.toast?.show(`讀取節點失敗：${error.message}`, { type: "danger", duration: 12000 });
      }
    }

    function scheduleRefresh(kind = "runListOnly") {
      const normalizedKind = kind === "currentRunGraph" ? "currentRunGraph" : "runListOnly";
      if (normalizedKind === "currentRunGraph" || !local.pendingRefreshKind) {
        local.pendingRefreshKind = normalizedKind;
      }
      if (local.refreshTimer || local.refreshInFlight) return;
      local.refreshTimer = window.setTimeout(async () => {
        local.refreshTimer = null;
        const nextKind = local.pendingRefreshKind;
        local.pendingRefreshKind = null;
        if (!nextKind) return;
        local.refreshInFlight = true;
        try {
          if (nextKind === "currentRunGraph" && local.runId) {
            await loadGraph(local.runId, { preserveSelection: true, preserveDrawer: true, silent: true });
          } else {
            await loadRuns({ preserveSelection: true });
          }
        } finally {
          local.refreshInFlight = false;
          if (local.pendingRefreshKind) {
            scheduleRefresh(local.pendingRefreshKind);
          }
        }
      }, REFRESH_THROTTLE_MS);
    }

    function subscribeGraphLiveUpdates() {
      if (typeof local.unsubscribeLiveUpdates === "function") return;
      const unsubscribers = [];
      logUiDebug("graph.live-subscriptions", { action: "subscribe", active_subscribers: 0 });
      const handleLiveEvent = ({ eventType = "", data = {} } = {}) => {
        const type = String(eventType || "").toLowerCase();
        if (!type) return;
        const eventRunId = String(data?.run_id || data?.runId || "").trim();
        const selectedRunId = String(local.runId || "").trim();
        if (["run", "run.update", "node.update", "done"].includes(type)) {
          if (eventRunId && selectedRunId && eventRunId === selectedRunId) {
            scheduleRefresh("currentRunGraph");
            return;
          }
          if (eventRunId && selectedRunId && eventRunId !== selectedRunId) {
            scheduleRefresh("runListOnly");
            return;
          }
          if (type === "done" || type === "run" || type === "run.update") {
            scheduleRefresh(selectedRunId ? "currentRunGraph" : "runListOnly");
          }
        }
      };

      const uiStore = ctx.appState?.uiStore;
      if (uiStore?.subscribe) {
        let previousRunId = String(uiStore.getState?.()?.run?.run_id || "");
        const unsubscribeUiStore = uiStore.subscribe((snapshot = {}) => {
          const currentRunId = String(snapshot?.run?.run_id || "");
          if (currentRunId && currentRunId === String(local.runId || "")) {
            scheduleRefresh("currentRunGraph");
          } else if (currentRunId && currentRunId !== previousRunId) {
            scheduleRefresh("runListOnly");
          }
          previousRunId = currentRunId;
        });
        unsubscribers.push(unsubscribeUiStore);
        logUiDebug("graph.live-subscriptions", { action: "subscribe", source: "uiStore", active_subscribers: unsubscribers.length });
      }

      const unsubscribeBus = ctx.bus?.on?.("stream:event", handleLiveEvent);
      if (typeof unsubscribeBus === "function") {
        unsubscribers.push(unsubscribeBus);
        logUiDebug("graph.live-subscriptions", { action: "subscribe", source: "bus", active_subscribers: unsubscribers.length });
      }

      local.unsubscribeLiveUpdates = () => {
        unsubscribers.forEach((fn) => fn?.());
        logUiDebug("graph.live-subscriptions", { action: "unsubscribe", active_subscribers: 0 });
        unsubscribers.length = 0;
      };
    }

    function unsubscribeGraphLiveUpdates() {
      local.unsubscribeLiveUpdates?.();
      local.unsubscribeLiveUpdates = null;
      if (local.refreshTimer) {
        window.clearTimeout(local.refreshTimer);
        local.refreshTimer = null;
      }
      local.pendingRefreshKind = null;
      local.refreshInFlight = false;
    }

    function renderGraphPreviewNotice({
      message,
      detail = "",
      refreshable = false,
      level = "empty",
    }) {
      const noticeEl = document.createElement("p");
      noticeEl.className = `graph-empty-state graph-empty-state--${level}`;
      const messageEl = document.createElement("span");
      messageEl.textContent = message;
      noticeEl.appendChild(messageEl);
      if (detail) {
        const detailEl = document.createElement("small");
        detailEl.textContent = detail;
        noticeEl.appendChild(detailEl);
      }
      if (refreshable) {
        const buttonEl = document.createElement("button");
        buttonEl.type = "button";
        buttonEl.className = "btn btn-sm";
        buttonEl.dataset.graphAction = "reload";
        buttonEl.textContent = "重新整理頁面";
        buttonEl.addEventListener("click", () => {
          window.location.reload();
        });
        noticeEl.appendChild(buttonEl);
      }
      previewEl.replaceChildren(noticeEl);
      local.layoutModel = null;
      local.exportableSvg = "";
      local.canvasNodeEls.clear();
    }

    function syncAutoFocus(viewModel) {
      const nextAutoFocusNodeId = String(viewModel?.preferredFocusNodeId || "").trim();
      const changed = nextAutoFocusNodeId && nextAutoFocusNodeId !== local.autoFocusNodeId;
      local.autoFocusNodeId = nextAutoFocusNodeId;
      updateSelectedState();
      if (!changed) return;
      const nodeEl = local.canvasNodeEls.get(nextAutoFocusNodeId);
      nodeEl?.scrollIntoView?.({ behavior: "smooth", block: "center", inline: "center" });
    }

    function renderGraphCanvas(viewModel) {
      const layoutModel = createGraphLayout(viewModel);
      local.layoutModel = layoutModel;
      local.exportableSvg = buildGraphCanvasSvg(layoutModel);
      local.canvasNodeEls.clear();

      const canvasEl = document.createElement("div");
      canvasEl.className = "graph-flow-canvas";
      canvasEl.style.width = `${layoutModel.width}px`;
      canvasEl.style.height = `${layoutModel.height}px`;

      const svgEl = createSvgElement("svg", {
        class: "graph-flow-svg",
        viewBox: `0 0 ${layoutModel.width} ${layoutModel.height}`,
        width: layoutModel.width,
        height: layoutModel.height,
        "aria-hidden": "true",
      });

      const defsEl = createSvgElement("defs");
      [
        ["idle", "#94a3b8"],
        ["active", "#2563eb"],
        ["ready", "#d97706"],
        ["complete", "#059669"],
        ["failed", "#dc2626"],
      ].forEach(([name, color]) => {
        const markerEl = createSvgElement("marker", {
          id: `graph-flow-arrow-${name}`,
          viewBox: "0 0 10 10",
          refX: "9",
          refY: "5",
          markerWidth: "8",
          markerHeight: "8",
          orient: "auto-start-reverse",
        });
        markerEl.appendChild(createSvgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: color }));
        defsEl.appendChild(markerEl);
      });
      svgEl.appendChild(defsEl);

      layoutModel.edges.forEach((edge) => {
        const groupEl = createSvgElement("g", { class: `graph-flow-edge graph-flow-edge--${edge.tone}` });
        groupEl.appendChild(createSvgElement("path", {
          d: edge.path,
          class: "graph-flow-edge__path",
          "marker-end": `url(#graph-flow-arrow-${edge.tone})`,
        }));
        if (edge.label) {
          const labelEl = createSvgElement("text", {
            x: edge.labelPosition.x,
            y: edge.labelPosition.y,
            class: "graph-flow-edge__label",
            "text-anchor": "middle",
          });
          labelEl.textContent = edge.label;
          groupEl.appendChild(labelEl);
        }
        svgEl.appendChild(groupEl);
      });

      const columnLayerEl = document.createElement("div");
      columnLayerEl.className = "graph-flow-columns";
      layoutModel.columns.forEach((column) => {
        const columnEl = document.createElement("div");
        columnEl.className = "graph-flow-column";
        columnEl.style.left = `${column.x}px`;
        columnEl.style.top = `${column.y}px`;
        columnEl.style.width = `${column.width}px`;
        columnEl.style.height = `${column.height}px`;
        columnEl.innerHTML = `<span class="graph-flow-column__label">${escapeHtml(column.label)}</span>`;
        columnLayerEl.appendChild(columnEl);
      });

      const nodeLayerEl = document.createElement("div");
      nodeLayerEl.className = "graph-flow-nodes";
      layoutModel.nodes.forEach((nodeVm) => {
        const nodeId = nodeVm.id;
        const nodeEl = document.createElement("button");
        nodeEl.type = "button";
        nodeEl.className = `graph-flow-node graph-flow-node--${nodeVm.flowRole}`;
        nodeEl.dataset.nodeId = nodeId;
        nodeEl.style.left = `${nodeVm.box.x}px`;
        nodeEl.style.top = `${nodeVm.box.y}px`;
        nodeEl.style.width = `${nodeVm.box.width}px`;
        nodeEl.style.height = `${nodeVm.box.height}px`;
        nodeEl.setAttribute("aria-label", `查看 ${nodeVm.displayTitle || nodeId} 節點詳細資訊`);
        nodeEl.innerHTML = buildNodeCardMarkup(nodeVm);
        nodeEl.addEventListener("click", (event) => {
          event.stopPropagation();
          void selectNode(nodeId);
        });
        local.canvasNodeEls.set(nodeId, nodeEl);
        nodeLayerEl.appendChild(nodeEl);
      });

      canvasEl.appendChild(svgEl);
      canvasEl.appendChild(columnLayerEl);
      canvasEl.appendChild(nodeLayerEl);
      previewEl.replaceChildren(canvasEl);
      syncAutoFocus(viewModel);
    }

    async function renderGraph(payload) {
      const viewModel = buildGraphRuntimeViewModel({
        graphPayload: payload,
        runMeta: { run_id: local.runId, run_status: payload?.run_status },
      });
      local.viewModel = viewModel;
      if (viewModel.diagnostics.length) {
        logUiDebug("graph.view-model", {
          run_id: viewModel.runId,
          diagnostics: viewModel.diagnostics,
          node_count: viewModel.nodes.length,
        });
      }

      codeEl.textContent = formatJson(viewModel.graph || {});
      listEl.innerHTML = "";
      local.listNodeEls.clear();

      if (!viewModel.nodes.length) {
        listEl.innerHTML = '<li><p class="graph-empty-state">目前沒有可顯示的節點資料。</p></li>';
        renderGraphPreviewNotice({
          message: "此 Run 尚無可視化節點資料",
          detail: "請確認 graph.resolved.json 是否已有 nodes / edges。",
        });
        renderGraphNodeDrawer(null);
        return;
      }

      viewModel.nodes.forEach((nodeVm) => {
        const li = document.createElement("li");
        li.className = "graph-node-item";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `graph-node-item__button graph-node-item__button--${nodeVm.flowRole} list-row`;
        btn.dataset.nodeId = nodeVm.id;
        btn.innerHTML = `
          <span class="graph-node-item__content">
            <strong class="graph-node-item__title">${escapeHtml(formatNodeIndex(nodeVm.order))} · ${escapeHtml(nodeVm.displayTitle || nodeVm.id || "(unknown node)")}</strong>
            <span class="graph-node-item__meta">${escapeHtml(getNodeMetaTokens(nodeVm).slice(0, 3).join(" · "))}</span>
          </span>
          <span class="node-status ${escapeHtml(nodeVm.statusUi.cssClass)}">${escapeHtml(nodeVm.statusUi.label)}</span>
        `;
        li.appendChild(btn);
        listEl.appendChild(li);
        local.listNodeEls.set(nodeVm.id, btn);
      });

      renderGraphCanvas(viewModel);
      if (local.selectedNodeId && !viewModel.nodes.some((node) => node.id === local.selectedNodeId)) {
        local.selectedNodeId = "";
        renderGraphNodeDrawer(null);
        closeGraphNodeDrawer();
      } else {
        updateSelectedState();
      }
    }

    async function loadRuns(options = {}) {
      const { preserveSelection = false } = options;
      const projectId = getProjectId(ctx);
      const runs = await ctx.services.graph.listRuns(projectId);
      const previousSelectedRunId = String(local.runId || "");
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

      const resolvedPreferredRunId = preserveSelection
        ? previousSelectedRunId
        : (preferredRunId || "");
      local.runId = resolvedPreferredRunId || preferredRunId || runs[0]?.id || runs[0]?.run_id || "";
      runSelectEl.value = local.runId;
    }

    async function loadGraph(runId = "", options = {}) {
      const { preserveSelection = false, preserveDrawer = false, silent = false } = options;
      if (!runId) {
        previewEl.innerHTML = '<p class="empty-context">請先選擇 Run。</p>';
        codeEl.textContent = "";
        listEl.innerHTML = "";
        local.selectedNodeId = "";
        local.autoFocusNodeId = "";
        local.layoutModel = null;
        local.exportableSvg = "";
        renderGraphNodeDrawer(null);
        closeGraphNodeDrawer();
        return;
      }
      local.runId = runId;
      const previousSelectedNodeId = String(local.selectedNodeId || "");
      const shouldKeepSelection = preserveSelection && previousSelectedNodeId;
      if (!shouldKeepSelection) {
        local.selectedNodeId = "";
      }
      try {
        const graphPayload = await ctx.services.graph.getGraph(runId, getProjectId(ctx));
        runMetaEl.textContent = `Run：${runId}（${graphPayload?.run_status || "unknown"}）`;
        if (copyRunIdEl) {
          copyRunIdEl.disabled = false;
          copyRunIdEl.dataset.runId = runId;
        }
        await renderGraph(graphPayload || {});
        if (shouldKeepSelection && local.viewModel?.nodes?.some((node) => node.id === previousSelectedNodeId)) {
          local.selectedNodeId = previousSelectedNodeId;
          updateSelectedState();
          if (preserveDrawer && drawerEl && !drawerEl.hidden) {
            await selectNode(previousSelectedNodeId, { forceRefresh: true, openDrawer: true });
          }
        } else {
          renderGraphNodeDrawer(null);
          if (!preserveDrawer) closeGraphNodeDrawer();
        }
      } catch (error) {
        if (copyRunIdEl) {
          copyRunIdEl.disabled = true;
          copyRunIdEl.dataset.runId = "";
        }
        if (!silent) {
          ctx.ui.toast?.show(`載入 Graph 失敗：${error.message}`, { type: "danger", duration: 12000 });
        }
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
      void selectNode(node.dataset.nodeId || "");
    };

    const onRunChange = () => {
      void loadGraph(runSelectEl.value);
    };

    const onDrawerClose = () => {
      closeGraphNodeDrawer();
    };

    const onDocumentKeyDown = (event) => {
      if (event.key !== "Escape") return;
      closeGraphNodeDrawer();
    };

    const onDocumentClick = (event) => {
      if (!drawerEl || drawerEl.hidden) return;
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.closest("#graph-node-drawer")) return;
      if (target.closest("#graph-node-list") || target.closest("#graph-preview")) return;
      closeGraphNodeDrawer();
    };

    const onCopyGraphSource = async () => {
      const graphSource = String(codeEl?.textContent || "").trim();
      if (!graphSource) {
        ctx.ui.toast?.show("無 Graph JSON 內容", { type: "warning", duration: 12000 });
        return;
      }
      await copyText(graphSource, {
        toast: (message, options) => ctx.ui.toast?.show(message, options),
        successMessage: "Graph JSON 已複製到剪貼簿",
        errorMessage: "複製 Graph JSON 失敗，請手動複製",
      });
    };

    const onExportSvg = () => {
      if (!local.exportableSvg) {
        ctx.ui.toast?.show("尚未完成渲染", { type: "warning", duration: 12000 });
        return;
      }
      const runId = String(local.runId || "").trim();
      const fallback = new Date().toISOString().replace(/[:.]/g, "-");
      const ok = downloadTextFile(`graph-${runId || fallback}.svg`, local.exportableSvg, "image/svg+xml;charset=utf-8");
      if (!ok) {
        ctx.ui.toast?.show("SVG 匯出失敗，請稍後再試", { type: "danger", duration: 12000 });
        return;
      }
      ctx.ui.toast?.show("SVG 匯出完成", { type: "success" });
    };

    listEl.addEventListener("click", onListClick);
    runSelectEl?.addEventListener("change", onRunChange);
    refreshEl?.addEventListener("click", () => void load());
    copyGraphEl?.addEventListener("click", onCopyGraphSource);
    exportSvgEl?.addEventListener("click", onExportSvg);
    drawerCloseEl?.addEventListener("click", onDrawerClose);
    document.addEventListener("keydown", onDocumentKeyDown);
    document.addEventListener("click", onDocumentClick);
    subscribeGraphLiveUpdates();
    renderGraphNodeDrawer(null);

    GRAPH_VIEW.__graphCleanup = () => {
      listEl.removeEventListener("click", onListClick);
      runSelectEl?.removeEventListener("change", onRunChange);
      drawerCloseEl?.removeEventListener("click", onDrawerClose);
      copyGraphEl?.removeEventListener("click", onCopyGraphSource);
      exportSvgEl?.removeEventListener("click", onExportSvg);
      document.removeEventListener("keydown", onDocumentKeyDown);
      document.removeEventListener("click", onDocumentClick);
      unsubscribeGraphLiveUpdates();
      closeGraphNodeDrawer();
    };
    GRAPH_VIEW.__graphLoad = load;
  },
  unmount() {
    GRAPH_VIEW.__graphCleanup?.();
    GRAPH_VIEW.__graphCleanup = null;
    GRAPH_VIEW.__graphLoad = null;
  },
  onRoute: async () => {
    await GRAPH_VIEW.__graphLoad?.();
  },
};
