const STATUS_MAP = {
  queued: "pending",
  waiting: "pending",
  pending: "pending",
  running: "running",
  in_progress: "running",
  processing: "running",
  done: "succeeded",
  completed: "succeeded",
  success: "succeeded",
  succeeded: "succeeded",
  ok: "succeeded",
  error: "failed",
  failed: "failed",
  failure: "failed",
  cancelled: "failed",
  canceled: "failed",
  timeout: "failed",
};

const STATUS_UI = {
  pending: { tag: "pending", label: "等待中", cssClass: "node-status--pending", mermaidClass: "node-status--pending" },
  running: { tag: "running", label: "執行中", cssClass: "node-status--running", mermaidClass: "node-status--running" },
  succeeded: { tag: "succeeded", label: "成功", cssClass: "node-status--succeeded", mermaidClass: "node-status--succeeded" },
  failed: { tag: "failed", label: "失敗", cssClass: "node-status--failed", mermaidClass: "node-status--failed" },
  unknown: { tag: "unknown", label: "未知", cssClass: "node-status--unknown", mermaidClass: "node-status--unknown" },
};

export const GRAPH_STATUS_CLASS_LIST = Object.freeze(Object.values(STATUS_UI).map((item) => item.cssClass));

const NODE_ICON_MAP = {
  agent: "smart_toy",
  task: "account_tree",
  tool: "build",
  map: "hub",
  write_file: "description",
  file: "description",
  artifact: "inventory_2",
  condition: "rule",
  default: "account_tree",
};

function normalizeStatus(rawStatus) {
  const key = String(rawStatus || "").trim().toLowerCase();
  return STATUS_MAP[key] || "unknown";
}

function firstNonEmptyText(...values) {
  for (const value of values) {
    const text = String(value || "").trim();
    if (text) return text;
  }
  return "";
}

function sanitizeInlineText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function truncateText(value, limit = 120) {
  const text = sanitizeInlineText(value);
  if (!text || text.length <= limit) return text;
  return `${text.slice(0, limit)}…`;
}

function formatProgress(rawValue) {
  const numeric = Number(rawValue);
  if (!Number.isFinite(numeric)) return null;
  return Math.max(0, Math.min(100, numeric));
}

function normalizeNodeType(graphNode = {}) {
  return firstNonEmptyText(graphNode.node_type, graphNode.type, "task").toLowerCase();
}

function formatNodeTypeLabel(nodeType = "") {
  const normalized = String(nodeType || "").trim();
  if (!normalized) return "TASK";
  return normalized.replace(/[_-]+/g, " ").toUpperCase();
}

function inferExecutor(graphNode = {}) {
  const taskSpec = graphNode.taskSpec && typeof graphNode.taskSpec === "object" ? graphNode.taskSpec : {};
  return firstNonEmptyText(taskSpec.executor, graphNode.executor);
}

function inferNodeIcon(nodeType, executor) {
  const normalizedExecutor = String(executor || "").trim().toLowerCase();
  if (normalizedExecutor && NODE_ICON_MAP[normalizedExecutor]) return NODE_ICON_MAP[normalizedExecutor];
  return NODE_ICON_MAP[nodeType] || NODE_ICON_MAP.default;
}

function buildNodeDisplayTitle(graphNode = {}, nodeId = "") {
  const display = graphNode.taskSpec && typeof graphNode.taskSpec === "object" && graphNode.taskSpec.display && typeof graphNode.taskSpec.display === "object"
    ? graphNode.taskSpec.display
    : {};
  return firstNonEmptyText(display.label, graphNode.title, graphNode.name, nodeId, "(unknown node)");
}

function buildNodeDisplaySummary(graphNode = {}) {
  const taskSpec = graphNode.taskSpec && typeof graphNode.taskSpec === "object" ? graphNode.taskSpec : {};
  const display = taskSpec.display && typeof taskSpec.display === "object" ? taskSpec.display : {};
  return truncateText(firstNonEmptyText(
    display.summary,
    graphNode.description,
    graphNode.goal,
    graphNode.prompt,
    graphNode.instructions,
    taskSpec.agent?.prompt,
    taskSpec.agent?.instructions,
    graphNode.path,
  ), 110);
}

function normalizeEdge(edge = {}) {
  const from = firstNonEmptyText(edge.from, edge.from_node);
  const to = firstNonEmptyText(edge.to, edge.to_node);
  if (!from || !to) return null;
  const kind = firstNonEmptyText(edge.kind);
  const edgeType = firstNonEmptyText(edge.edge_type, edge.type);
  const when = edge.when;
  const labelParts = [];
  if (kind) labelParts.push(kind);
  if (edgeType) labelParts.push(edgeType);
  if (typeof when === "boolean") labelParts.push(`when:${when}`);
  return {
    ...edge,
    from,
    to,
    kind,
    edgeType,
    when,
    label: labelParts.join(" · "),
  };
}

function average(values = [], fallback = 0) {
  const numeric = values.filter((value) => Number.isFinite(value));
  if (!numeric.length) return fallback;
  return numeric.reduce((sum, value) => sum + value, 0) / numeric.length;
}

function pickStatusSource(nodeState = {}, graphNode = {}) {
  if (nodeState && typeof nodeState === "object") {
    const runtimeRaw = nodeState.status ?? nodeState.state;
    if (runtimeRaw !== undefined && runtimeRaw !== null && String(runtimeRaw).trim()) {
      return { status: normalizeStatus(runtimeRaw), source: "node_states", raw: runtimeRaw };
    }
  }
  if (graphNode && typeof graphNode === "object") {
    const graphRaw = graphNode.status ?? graphNode.state;
    if (graphRaw !== undefined && graphRaw !== null && String(graphRaw).trim()) {
      return { status: normalizeStatus(graphRaw), source: "graph", raw: graphRaw };
    }
  }
  return { status: "unknown", source: "fallback", raw: null };
}

export function mapGraphStatusToUi(status) {
  return STATUS_UI[normalizeStatus(status)] || STATUS_UI.unknown;
}

export function getGraphStatusClassList() {
  return GRAPH_STATUS_CLASS_LIST;
}

export function buildGraphRuntimeViewModel({ graphPayload = {}, nodeStates = null, runMeta = {} } = {}) {
  const diagnostics = [];
  const graph = graphPayload?.graph && typeof graphPayload.graph === "object" ? graphPayload.graph : (graphPayload || {});
  const graphNodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const graphEdges = Array.isArray(graph?.edges) ? graph.edges : [];
  const resolvedNodeStates = nodeStates && typeof nodeStates === "object"
    ? nodeStates
    : (graphPayload?.node_states && typeof graphPayload.node_states === "object" ? graphPayload.node_states : null);
  if (!resolvedNodeStates) diagnostics.push("node_states_missing");

  const originalOrder = new Map();
  const nodeIds = [];
  graphNodes.forEach((node, index) => {
    const nodeId = String(node?.id || "").trim();
    if (!nodeId) return;
    originalOrder.set(nodeId, index);
    nodeIds.push(nodeId);
  });
  const validNodeIds = new Set(nodeIds);
  const edges = graphEdges
    .map(normalizeEdge)
    .filter((edge) => edge && validNodeIds.has(edge.from) && validNodeIds.has(edge.to));
  const predecessorMap = new Map(nodeIds.map((nodeId) => [nodeId, []]));
  const successorMap = new Map(nodeIds.map((nodeId) => [nodeId, []]));
  edges.forEach((edge) => {
    predecessorMap.get(edge.to)?.push(edge.from);
    successorMap.get(edge.from)?.push(edge.to);
  });

  const indegreeMap = new Map(nodeIds.map((nodeId) => [nodeId, predecessorMap.get(nodeId)?.length || 0]));
  const levelMap = new Map(nodeIds.map((nodeId) => [nodeId, 0]));
  const readyQueue = nodeIds
    .filter((nodeId) => (indegreeMap.get(nodeId) || 0) === 0)
    .sort((left, right) => (originalOrder.get(left) ?? 0) - (originalOrder.get(right) ?? 0));
  const topologicalOrder = [];

  while (readyQueue.length) {
    const nodeId = readyQueue.shift();
    if (!nodeId) continue;
    topologicalOrder.push(nodeId);
    const nextLevel = (levelMap.get(nodeId) || 0) + 1;
    const successors = [...(successorMap.get(nodeId) || [])].sort((left, right) => (originalOrder.get(left) ?? 0) - (originalOrder.get(right) ?? 0));
    successors.forEach((successorId) => {
      levelMap.set(successorId, Math.max(levelMap.get(successorId) || 0, nextLevel));
      indegreeMap.set(successorId, (indegreeMap.get(successorId) || 0) - 1);
      if ((indegreeMap.get(successorId) || 0) === 0) readyQueue.push(successorId);
    });
    readyQueue.sort((left, right) => {
      const leftLevel = levelMap.get(left) || 0;
      const rightLevel = levelMap.get(right) || 0;
      if (leftLevel !== rightLevel) return leftLevel - rightLevel;
      return (originalOrder.get(left) ?? 0) - (originalOrder.get(right) ?? 0);
    });
  }

  if (topologicalOrder.length < nodeIds.length) {
    diagnostics.push("graph_cycle_detected");
    const processed = new Set(topologicalOrder);
    let fallbackLevel = Math.max(0, ...topologicalOrder.map((nodeId) => levelMap.get(nodeId) || 0));
    nodeIds
      .filter((nodeId) => !processed.has(nodeId))
      .sort((left, right) => (originalOrder.get(left) ?? 0) - (originalOrder.get(right) ?? 0))
      .forEach((nodeId) => {
        fallbackLevel += 1;
        levelMap.set(nodeId, fallbackLevel);
        topologicalOrder.push(nodeId);
      });
  }

  const orderMap = new Map(topologicalOrder.map((nodeId, index) => [nodeId, index]));
  const laneMap = new Map();
  const orderedLevels = [...new Set(topologicalOrder.map((nodeId) => levelMap.get(nodeId) || 0))].sort((left, right) => left - right);
  orderedLevels.forEach((level) => {
    const idsAtLevel = topologicalOrder
      .filter((nodeId) => (levelMap.get(nodeId) || 0) === level)
      .sort((left, right) => {
        const leftPreds = predecessorMap.get(left) || [];
        const rightPreds = predecessorMap.get(right) || [];
        const leftAverage = average(leftPreds.map((nodeId) => laneMap.get(nodeId)), originalOrder.get(left) ?? 0);
        const rightAverage = average(rightPreds.map((nodeId) => laneMap.get(nodeId)), originalOrder.get(right) ?? 0);
        if (leftAverage !== rightAverage) return leftAverage - rightAverage;
        return (orderMap.get(left) ?? 0) - (orderMap.get(right) ?? 0);
      });
    idsAtLevel.forEach((nodeId, index) => laneMap.set(nodeId, index));
  });

  const nodes = graphNodes.map((node) => {
    const nodeId = String(node?.id || "").trim();
    const runtimeState = nodeId && resolvedNodeStates ? (resolvedNodeStates[nodeId] || {}) : {};
    const statusResult = pickStatusSource(runtimeState, node);
    const nodeType = normalizeNodeType(node);
    const executorLabel = inferExecutor(node);
    const progress = formatProgress(runtimeState.progress ?? node.progress);
    return {
      id: nodeId,
      graphNode: node,
      runtimeState,
      effectiveStatus: statusResult.status,
      statusSource: statusResult.source,
      statusRaw: statusResult.raw,
      statusUi: mapGraphStatusToUi(statusResult.status),
      nodeType,
      typeLabel: formatNodeTypeLabel(nodeType),
      executorLabel: executorLabel || "",
      displayTitle: buildNodeDisplayTitle(node, nodeId),
      displaySummary: buildNodeDisplaySummary(node),
      iconName: inferNodeIcon(nodeType, executorLabel),
      progress,
      predecessorIds: predecessorMap.get(nodeId) || [],
      successorIds: successorMap.get(nodeId) || [],
      order: orderMap.get(nodeId) ?? (originalOrder.get(nodeId) ?? 0),
      level: levelMap.get(nodeId) ?? 0,
      lane: laneMap.get(nodeId) ?? 0,
    };
  });

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const runningIds = nodes.filter((node) => node.effectiveStatus === "running").map((node) => node.id);
  const failedIds = nodes.filter((node) => node.effectiveStatus === "failed").map((node) => node.id);
  const readyIds = new Set(
    nodes
      .filter((node) => node.effectiveStatus === "pending" && node.predecessorIds.every((nodeId) => nodeById.get(nodeId)?.effectiveStatus === "succeeded"))
      .map((node) => node.id),
  );

  const enrichedNodes = nodes.map((node) => {
    const isReady = readyIds.has(node.id);
    const isCurrent = node.effectiveStatus === "running";
    const isFailed = node.effectiveStatus === "failed";
    const isCompleted = node.effectiveStatus === "succeeded";
    const isQueued = !isCurrent && node.effectiveStatus === "pending" && isReady && runningIds.length > 0;
    const isNext = !isCurrent && node.effectiveStatus === "pending" && isReady && runningIds.length === 0;
    const isBlocked = node.effectiveStatus === "pending" && !isReady && node.predecessorIds.length > 0;
    let flowRole = "idle";
    if (isCurrent) flowRole = "current";
    else if (isFailed) flowRole = "failed";
    else if (isCompleted) flowRole = "completed";
    else if (isNext) flowRole = "next";
    else if (isQueued) flowRole = "queued";
    else if (isBlocked) flowRole = "blocked";
    else if (node.effectiveStatus === "unknown") flowRole = "unknown";
    return {
      ...node,
      isReady,
      isCurrent,
      isFailed,
      isCompleted,
      isQueued,
      isNext,
      isBlocked,
      flowRole,
    };
  });

  const preferredFocusNodeId = [...enrichedNodes]
    .sort((left, right) => left.order - right.order)
    .find((node) => node.isCurrent)?.id
    || [...enrichedNodes].sort((left, right) => left.order - right.order).find((node) => node.isFailed)?.id
    || [...enrichedNodes].sort((left, right) => left.order - right.order).find((node) => node.isNext)?.id
    || [...enrichedNodes].sort((left, right) => left.order - right.order).find((node) => node.isQueued)?.id
    || [...enrichedNodes].sort((left, right) => left.order - right.order)[0]?.id
    || "";

  return {
    runId: runMeta.run_id || graphPayload?.run_id || null,
    runStatus: runMeta.run_status || graphPayload?.run_status || null,
    graph,
    graphMermaid: graphPayload?.graph_mermaid || "",
    nodeStates: resolvedNodeStates || {},
    nodes: enrichedNodes,
    edges,
    preferredFocusNodeId,
    diagnostics,
  };
}
