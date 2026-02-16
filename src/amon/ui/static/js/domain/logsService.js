export function createLogsService({ api }) {
  return {
    getLogs(runId, projectId = "") {
      const params = new URLSearchParams();
      if (runId) params.set("run_id", runId);
      if (projectId) params.set("project_id", projectId);
      return api.request(`/logs/query?${params.toString()}`);
    },
    streamLogs(runId) {
      const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
      return new EventSource(`/v1/logs/stream${query}`);
    },
  };
}
