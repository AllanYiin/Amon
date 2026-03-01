import { logUiDebug, logViewInitDebug } from "../utils/debug.js";
import { buildGraphRuntimeViewModel, getGraphStatusClassList } from "../domain/graphRuntimeAdapter.js";
import { copyText } from "../utils/clipboard.js";

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
    const copyMermaidEl = rootEl.querySelector("#graph-copy-mermaid");
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
      graph: null,
      panZoom: null,
      runId: "",
      viewModel: null,
      selectedNodeId: "",
      nodeDetails: new Map(),
      svgNodeGroups: new Map(),
      unsubscribeLiveUpdates: null,
      refreshTimer: null,
      pendingRefreshKind: null,
      refreshInFlight: false,
    };

    const REFRESH_THROTTLE_MS = 450;
    const STATUS_CLASS_LIST = getGraphStatusClassList();

    function closeGraphNodeDrawer() {
      if (!drawerEl) return;
      drawerEl.hidden = true;
    }

    function openGraphNodeDrawer() {
      if (!drawerEl) return;
      drawerEl.hidden = false;
    }

    function updateSelectedState() {
      const selectedNodeId = String(local.selectedNodeId || "").trim();
      listEl.querySelectorAll("[data-node-id]").forEach((buttonEl) => {
        const isSelected = buttonEl.getAttribute("data-node-id") === selectedNodeId;
        buttonEl.classList.toggle("is-selected", isSelected);
        buttonEl.setAttribute("aria-pressed", isSelected ? "true" : "false");
      });
      local.svgNodeGroups.forEach((groups, nodeId) => {
        const isSelected = nodeId === selectedNodeId;
        groups.forEach((group) => group.classList.toggle("graph-node--selected", isSelected));
      });
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

    function buildLabelToNodeIds(viewModel) {
      const map = new Map();
      (viewModel?.nodes || []).forEach((nodeVm) => {
        const graphNode = nodeVm?.graphNode || {};
        const keys = new Set([
          nodeVm.id,
          graphNode.id,
          graphNode.label,
          graphNode.name,
          graphNode.title,
          graphNode.display_name,
        ]
          .map((value) => String(value || "").trim())
          .filter(Boolean));
        keys.forEach((key) => {
          const existing = map.get(key) || [];
          if (!existing.includes(nodeVm.id)) existing.push(nodeVm.id);
          map.set(key, existing);
        });
      });
      return map;
    }

    function resolveNodeIdFromSvgGroup(groupEl, viewModel, labelMap) {
      const rawCandidates = [
        groupEl?.dataset?.nodeId,
        groupEl?.dataset?.id,
        groupEl?.getAttribute?.("data-node-id"),
        groupEl?.getAttribute?.("data-id"),
        groupEl?.id,
        groupEl?.querySelector?.("title")?.textContent,
      ];
      const nodeIds = new Set((viewModel?.nodes || []).map((node) => node.id));
      for (const candidate of rawCandidates) {
        const normalized = String(candidate || "").trim();
        if (normalized && nodeIds.has(normalized)) return normalized;
      }
      const label = String(groupEl?.querySelector?.(".nodeLabel")?.textContent || "").trim();
      if (!label) return "";
      const matchedIds = labelMap.get(label) || [];
      if (matchedIds.length > 1) {
        logUiDebug("graph.svg-node-ambiguous-label", { label, node_ids: matchedIds });
      }
      return matchedIds[0] || "";
    }

    function bindMermaidNodeClick() {
      local.svgNodeGroups = new Map();
      const svgRoot = previewEl.querySelector("svg");
      if (!svgRoot || !local.viewModel) return { groupCount: 0, boundCount: 0 };
      const labelMap = buildLabelToNodeIds(local.viewModel);
      const groups = svgRoot.querySelectorAll("g.node");
      let boundCount = 0;
      groups.forEach((group) => {
        const nodeId = resolveNodeIdFromSvgGroup(group, local.viewModel, labelMap);
        if (!nodeId) return;
        const vmNode = local.viewModel.nodes.find((node) => node.id === nodeId);
        if (vmNode?.statusUi?.mermaidClass) {
          group.classList.add(vmNode.statusUi.mermaidClass);
        }
        const list = local.svgNodeGroups.get(nodeId) || [];
        list.push(group);
        local.svgNodeGroups.set(nodeId, list);
        group.style.cursor = "pointer";
        group.setAttribute("role", "button");
        group.setAttribute("tabindex", "0");
        group.setAttribute("aria-label", `開啟 ${nodeId} 節點詳細資訊`);
        group.addEventListener("pointerdown", (event) => {
          group.dataset.downX = String(event.clientX);
          group.dataset.downY = String(event.clientY);
        });
        group.addEventListener("click", (event) => {
          event.stopPropagation();
          const downX = Number(group.dataset.downX || event.clientX);
          const downY = Number(group.dataset.downY || event.clientY);
          const moved = Math.hypot(event.clientX - downX, event.clientY - downY);
          if (moved > 6) return;
          void selectNode(nodeId);
        });
        group.addEventListener("keydown", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          void selectNode(nodeId);
        });
        boundCount += 1;
      });
      updateSelectedState();
      return { groupCount: groups.length, boundCount };
    }

    function renderGraphPreviewNotice({
      message,
      detail = "",
      refreshable = false,
      level = "empty",
      keepSvg = false,
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
      if (keepSvg) {
        previewEl.insertAdjacentElement("afterbegin", noticeEl);
      } else {
        previewEl.innerHTML = "";
        previewEl.appendChild(noticeEl);
      }
    }

    function updateGraphNodeStatusDom(viewModel) {
      const nodesById = new Map((viewModel?.nodes || []).map((node) => [node.id, node]));
      listEl.querySelectorAll("[data-node-id]").forEach((buttonEl) => {
        const nodeId = String(buttonEl.getAttribute("data-node-id") || "").trim();
        const nodeVm = nodesById.get(nodeId);
        if (!nodeVm) return;
        const statusEl = buttonEl.querySelector(".node-status");
        if (!(statusEl instanceof HTMLElement)) return;
        statusEl.className = `node-status ${nodeVm.statusUi.cssClass}`;
        statusEl.textContent = nodeVm.statusUi.label;
      });
      local.svgNodeGroups.forEach((groups, nodeId) => {
        const nodeVm = nodesById.get(nodeId);
        groups.forEach((group) => {
          group.classList.remove(...STATUS_CLASS_LIST);
          group.classList.add(nodeVm?.statusUi?.mermaidClass || "node-status--unknown");
        });
      });
      updateSelectedState();
    }

    async function renderGraph(payload, nodeStates = null, options = {}) {
      const { allowIncrementalUpdate = false } = options;
      const viewModel = buildGraphRuntimeViewModel({
        graphPayload: payload,
        nodeStates,
        runMeta: { run_id: local.runId, run_status: payload?.run_status },
      });
      const canIncrementalUpdate = allowIncrementalUpdate
        && !!local.viewModel
        && local.viewModel.graphMermaid === viewModel.graphMermaid
        && local.svgNodeGroups.size > 0;

      if (canIncrementalUpdate) {
        local.viewModel = viewModel;
        updateGraphNodeStatusDom(viewModel);
        return;
      }

      local.viewModel = viewModel;
      if (viewModel.diagnostics.length) {
        logUiDebug("graph.view-model", {
          run_id: viewModel.runId,
          diagnostics: viewModel.diagnostics,
          node_count: viewModel.nodes.length,
        });
      }
      const graph = viewModel.graph || {};
      local.graph = graph;
      codeEl.textContent = viewModel.graphMermaid || "";
      listEl.innerHTML = "";
      const nodes = Array.isArray(viewModel?.nodes) ? viewModel.nodes : [];
      if (!nodes.length) {
        listEl.innerHTML = '<li><p class="graph-empty-state">目前沒有可顯示的節點資料。</p></li>';
      }
      nodes.forEach((nodeVm) => {
        const node = nodeVm?.graphNode || {};
        const progressValue = Number.isFinite(Number(node?.progress)) ? Math.max(0, Math.min(100, Number(node.progress))) : null;
        const progressMeta = progressValue === null ? "" : `<span>${Math.round(progressValue)}%</span>`;
        const progressBlock = progressValue === null
          ? ""
          : `<div class="graph-node-item__progress" aria-label="Node progress"><span style="--graph-progress:${progressValue}%;"></span></div>`;
        const li = document.createElement("li");
        li.className = "graph-node-item";
        li.innerHTML = `
          <button type="button" class="graph-node-item__button list-row" data-node-id="${nodeVm.id}">
            <span class="graph-node-item__content">
              <strong class="graph-node-item__title">${nodeVm.id || "(unknown node)"}</strong>
              <span class="graph-node-item__meta">${progressMeta}${progressBlock}</span>
            </span>
            <span class="node-status ${nodeVm.statusUi.cssClass}">${nodeVm.statusUi.label}</span>
          </button>
        `;
        listEl.appendChild(li);
      });

      previewEl.innerHTML = "";
      local.panZoom?.destroy?.();
      local.panZoom = null;

      const graphMermaid = String(viewModel.graphMermaid || "").trim();
      if (!graphMermaid) {
        renderGraphPreviewNotice({
          message: "此 Run 尚無流程圖資料",
          detail: "請先查看下方 graph-code 區塊是否有內容。",
        });
      } else if (!window.__mermaid || typeof window.__mermaid.render !== "function") {
        logUiDebug("graph.mermaid-missing", {
          run_id: local.runId,
          has_graph_mermaid: true,
          mermaid_type: typeof window.__mermaid,
        });
        console.error("[graph] Mermaid library not loaded.", { run_id: local.runId });
        renderGraphPreviewNotice({
          message: "Mermaid 未載入（可能離線或資源被擋）",
          detail: "請嘗試重新整理頁面後再試一次。",
          refreshable: true,
          level: "warning",
        });
      } else {
        try {
          const { svg } = await window.__mermaid.render(`graph-preview-${Date.now()}`, graphMermaid);
          previewEl.innerHTML = svg;
          const svgEl = previewEl.querySelector("svg");
          if (svgEl && window.svgPanZoom) {
            local.panZoom = window.svgPanZoom(svgEl, { controlIconsEnabled: true, fit: true, center: true });
          }
          const { groupCount, boundCount } = bindMermaidNodeClick();
          if (groupCount === 0 || boundCount === 0) {
            logUiDebug("graph.mermaid-node-structure-unexpected", {
              run_id: local.runId,
              group_count: groupCount,
              bound_count: boundCount,
            });
            console.error("[graph] Mermaid SVG rendered but no recognizable nodes.", {
              run_id: local.runId,
              group_count: groupCount,
              bound_count: boundCount,
            });
            renderGraphPreviewNotice({
              message: "流程圖已渲染但無法識別節點",
              detail: "可能是 Mermaid 版本差異，請比對 g.node 結構。",
              level: "warning",
              keepSvg: true,
            });
          }
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : String(error || "unknown error");
          logUiDebug("graph.mermaid-render-failed", {
            run_id: local.runId,
            error_message: errorMessage,
          });
          console.error("[graph] Mermaid render failed.", { run_id: local.runId, error_message: errorMessage });
          renderGraphPreviewNotice({
            message: "流程圖渲染失敗",
            detail: `錯誤摘要：${errorMessage}`,
            level: "danger",
          });
        }
      }
      updateSelectedState();
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
        const fallbackNodeStates = ctx.appState?.graphRunId === runId ? (ctx.appState?.graphNodeStates || null) : null;
        await renderGraph(graphPayload || {}, fallbackNodeStates, { allowIncrementalUpdate: preserveSelection });
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

    const onCopyMermaid = async () => {
      const mermaidCode = String(codeEl?.textContent || "").trim();
      if (!mermaidCode) {
        ctx.ui.toast?.show("無 Mermaid 內容", { type: "warning", duration: 12000 });
        return;
      }
      await copyText(mermaidCode, {
        toast: (message, options) => ctx.ui.toast?.show(message, options),
        successMessage: "Mermaid 已複製到剪貼簿",
        errorMessage: "複製 Mermaid 失敗，請手動複製",
      });
    };

    const onExportSvg = () => {
      const svgEl = previewEl?.querySelector("svg");
      if (!(svgEl instanceof SVGElement)) {
        ctx.ui.toast?.show("尚未完成渲染", { type: "warning", duration: 12000 });
        return;
      }
      const rawSvg = String(svgEl.outerHTML || "").trim();
      if (!rawSvg) {
        ctx.ui.toast?.show("尚未完成渲染", { type: "warning", duration: 12000 });
        return;
      }
      const normalizedSvg = rawSvg.includes("xmlns=")
        ? rawSvg
        : rawSvg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
      const svgContent = `${normalizedSvg}\n`;
      const blob = new Blob([svgContent], { type: "image/svg+xml;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const runId = String(local.runId || "").trim();
      const fallback = new Date().toISOString().replace(/[:.]/g, "-");
      anchor.href = url;
      anchor.download = `graph-${runId || fallback}.svg`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      ctx.ui.toast?.show("SVG 匯出完成", { type: "success" });
    };

    listEl.addEventListener("click", onListClick);
    runSelectEl?.addEventListener("change", onRunChange);
    refreshEl?.addEventListener("click", () => void load());
    copyMermaidEl?.addEventListener("click", onCopyMermaid);
    exportSvgEl?.addEventListener("click", onExportSvg);
    drawerCloseEl?.addEventListener("click", onDrawerClose);
    document.addEventListener("keydown", onDocumentKeyDown);
    document.addEventListener("click", onDocumentClick);
    subscribeGraphLiveUpdates();
    renderGraphNodeDrawer(null);

    this.__graphCleanup = () => {
      listEl.removeEventListener("click", onListClick);
      runSelectEl?.removeEventListener("change", onRunChange);
      drawerCloseEl?.removeEventListener("click", onDrawerClose);
      copyMermaidEl?.removeEventListener("click", onCopyMermaid);
      exportSvgEl?.removeEventListener("click", onExportSvg);
      document.removeEventListener("keydown", onDocumentKeyDown);
      document.removeEventListener("click", onDocumentClick);
      unsubscribeGraphLiveUpdates();
      local.panZoom?.destroy?.();
      local.panZoom = null;
      closeGraphNodeDrawer();
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
