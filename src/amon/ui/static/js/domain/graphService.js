export function createGraphService({ api }) {
  return {
    async listRuns(projectId = "") {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      const payload = await api.request(`/runs${query}`);
      return payload.runs || [];
    },
    async getGraph(runId, projectId = "") {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/runs/${encodeURIComponent(runId)}/graph${query}`);
    },
    async getNodeDetail(runId, nodeId, projectId = "") {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(nodeId)}${query}`);
    },
  };
}
