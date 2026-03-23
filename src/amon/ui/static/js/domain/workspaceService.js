import { resolveAppUrl } from "../api.js";

export function createWorkspaceService({ api }) {
  return {
    async getProjectSummary(projectId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}`);
    },
    async listDefinitions(projectId, kind) {
      const payload = await api.request(`/projects/${encodeURIComponent(projectId)}/${encodeURIComponent(kind)}`);
      return payload[kind] || [];
    },
    async createRun(projectId, body) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/runs`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    async getRun(projectId, runId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}`);
    },
    async resumeRun(projectId, runId, body = {}) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/resume`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    async listUploads(projectId) {
      const payload = await api.request(`/projects/${encodeURIComponent(projectId)}/uploads`);
      return payload.uploads || [];
    },
    async createUpload(projectId, sourcePath, notes = "") {
      return api.request(`/projects/${encodeURIComponent(projectId)}/uploads`, {
        method: "POST",
        body: JSON.stringify({ source_path: sourcePath, notes }),
      });
    },
    async getUploadPreview(projectId, assetId) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/uploads/${encodeURIComponent(assetId)}/preview`);
    },
    async listConfirmations(projectId) {
      const payload = await api.request(`/projects/${encodeURIComponent(projectId)}/confirmations`);
      return payload.confirmations || [];
    },
    async approveConfirmation(projectId, confirmationId) {
      return api.request(
        `/projects/${encodeURIComponent(projectId)}/confirmations/${encodeURIComponent(confirmationId)}/approve`,
        { method: "POST", body: JSON.stringify({}) },
      );
    },
    async rejectConfirmation(projectId, confirmationId) {
      return api.request(
        `/projects/${encodeURIComponent(projectId)}/confirmations/${encodeURIComponent(confirmationId)}/reject`,
        { method: "POST", body: JSON.stringify({}) },
      );
    },
    streamRun(projectId, runId, { onEvent, onDone, onError }) {
      const source = new EventSource(
        resolveAppUrl(`/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/stream`),
      );
      source.onmessage = (event) => {
        if (typeof onEvent === "function") {
          onEvent("message", JSON.parse(event.data || "{}"));
        }
      };
      source.addEventListener("done", (event) => {
        if (typeof onDone === "function") {
          onDone(JSON.parse(event.data || "{}"));
        }
        source.close();
      });
      source.addEventListener("node.chunk", (event) => {
        if (typeof onEvent === "function") {
          onEvent("node.chunk", JSON.parse(event.data || "{}"));
        }
      });
      source.onerror = (error) => {
        if (typeof onError === "function") onError(error);
        source.close();
      };
      return () => source.close();
    },
  };
}
