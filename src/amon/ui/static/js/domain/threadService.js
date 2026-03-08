export function createThreadService({ api }) {
  return {
    async listProjectThreads(projectId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/threads`);
    },
    async createProjectThread(projectId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/threads`, {
        method: "POST",
        body: JSON.stringify({}),
      });
    },
    async setActiveThread(projectId, threadId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/active-thread`, {
        method: "PUT",
        body: JSON.stringify({ thread_id: threadId }),
      });
    },
    async getProjectThreadHistory(projectId, threadId = "") {
      const query = String(threadId || "").trim();
      if (query) {
        return api.request(`/projects/${encodeURIComponent(projectId)}/threads/${encodeURIComponent(query)}/history`);
      }
      return api.request(`/projects/${encodeURIComponent(projectId)}/history`);
    },
    async getProjectThreadContext(projectId, threadId = "") {
      const query = String(threadId || "").trim();
      if (query) {
        return api.request(`/projects/${encodeURIComponent(projectId)}/threads/${encodeURIComponent(query)}/context`);
      }
      return api.request(`/projects/${encodeURIComponent(projectId)}/context`);
    },
    async getProjectThreadContextStats(projectId, threadId = "") {
      const query = String(threadId || "").trim();
      if (query) {
        return api.request(`/projects/${encodeURIComponent(projectId)}/threads/${encodeURIComponent(query)}/context/stats`);
      }
      return api.request(`/projects/${encodeURIComponent(projectId)}/context/stats`);
    },
  };
}
