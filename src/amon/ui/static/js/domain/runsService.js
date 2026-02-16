function normalizeRun(run = {}) {
  if (!run || typeof run !== "object") return { id: "", status: "unknown", createdAt: "" };
  return {
    ...run,
    id: run.id || run.run_id || "",
    status: run.status || run.run_status || "unknown",
    createdAt: run.createdAt || run.created_at || run.ts || "",
  };
}

export function createRunsService({ api }) {
  return {
    normalizeRun,
    async listProjects() {
      const payload = await api.request("/projects");
      return payload.projects || [];
    },
    async listRuns(projectId) {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      const payload = await api.request(`/runs${query}`);
      return (payload.runs || []).map(normalizeRun);
    },
    async getRun(runId, projectId) {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      const payload = await api.request(`/runs/${encodeURIComponent(runId)}${query}`);
      return normalizeRun(payload.run || payload);
    },
    async getCurrentRun(projectId) {
      const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      const payload = await api.request(`/runs/current${query}`);
      return normalizeRun(payload.run || payload);
    },
    async setCurrentRun(projectId, runId) {
      return api.request("/runs/current", {
        method: "PUT",
        body: JSON.stringify({ project_id: projectId, run_id: runId }),
      });
    },
    async ensureChatSession(projectId) {
      return api.request("/chat/sessions", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId }),
      });
    },
    async getProjectHistory(projectId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/chat-history`);
    },
  };
}
