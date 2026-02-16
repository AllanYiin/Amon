function normalizeArtifact(artifact = {}) {
  return {
    ...artifact,
    id: artifact.id || artifact.artifact_id || artifact.path || artifact.name || "",
    name: artifact.name || artifact.path?.split("/").pop() || "(未命名)",
    mime: artifact.mime || artifact.content_type || "application/octet-stream",
    size: Number(artifact.size || artifact.bytes || 0),
    createdAt: artifact.createdAt || artifact.created_at || artifact.ts || "",
    url: artifact.url || artifact.preview_url || artifact.download_url || "",
  };
}

export function createArtifactsService({ api }) {
  return {
    normalizeArtifact,
    async listArtifacts(runId, projectId) {
      const params = new URLSearchParams();
      if (projectId) params.set("project_id", projectId);
      const query = params.toString();
      const payload = await api.request(`/runs/${encodeURIComponent(runId)}/artifacts${query ? `?${query}` : ""}`);
      return (payload.artifacts || []).map(normalizeArtifact);
    },
    getArtifactUrl(runId, artifactId) {
      return `/v1/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`;
    },
  };
}
