export function createGraphService({ api }) {
  return {
    async getGraph(runId, projectId = "") {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      const payload = await api.request(`/runs/${encodeURIComponent(runId)}/graph${query}`);
      return payload.graph || payload;
    },
    async getNodeDetail(runId, nodeId, projectId = "") {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(nodeId)}${query}`);
    },
  };
}
