export function createContextService({ api }) {
  return {
    async getContext(projectId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/context`);
    },
    async getContextStats(projectId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/context/stats`);
    },
    async saveContext(projectId, contextText) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/context`, {
        method: "PUT",
        body: JSON.stringify({ context: contextText }),
      });
    },
    async clearContext(scope = "project", projectId = "") {
      return api.request("/context/clear", {
        method: "POST",
        body: JSON.stringify({ scope, project_id: projectId }),
      });
    },
  };
}
