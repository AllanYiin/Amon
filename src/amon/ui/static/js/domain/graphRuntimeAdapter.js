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

function normalizeStatus(rawStatus) {
  const key = String(rawStatus || "").trim().toLowerCase();
  return STATUS_MAP[key] || "unknown";
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
  const resolvedNodeStates = nodeStates && typeof nodeStates === "object"
    ? nodeStates
    : (graphPayload?.node_states && typeof graphPayload.node_states === "object" ? graphPayload.node_states : null);
  if (!resolvedNodeStates) diagnostics.push("node_states_missing");

  const nodes = graphNodes.map((node) => {
    const nodeId = String(node?.id || "").trim();
    const runtimeState = nodeId && resolvedNodeStates ? (resolvedNodeStates[nodeId] || {}) : {};
    const statusResult = pickStatusSource(runtimeState, node);
    return {
      id: nodeId,
      graphNode: node,
      runtimeState,
      effectiveStatus: statusResult.status,
      statusSource: statusResult.source,
      statusRaw: statusResult.raw,
      statusUi: mapGraphStatusToUi(statusResult.status),
    };
  });

  return {
    runId: runMeta.run_id || graphPayload?.run_id || null,
    runStatus: runMeta.run_status || graphPayload?.run_status || null,
    graph,
    graphMermaid: graphPayload?.graph_mermaid || "",
    nodeStates: resolvedNodeStates || {},
    nodes,
    diagnostics,
  };
}
