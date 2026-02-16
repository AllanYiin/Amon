function normalizeDoc(doc = {}) {
  if (typeof doc === "string") {
    return { id: doc, name: doc.split("/").pop() || doc, path: doc, updatedAt: "" };
  }
  return {
    ...doc,
    id: doc.id || doc.doc_id || doc.path || doc.name || "",
    name: doc.name || doc.path?.split("/").pop() || "(未命名)",
    path: doc.path || doc.name || "",
    updatedAt: doc.updatedAt || doc.updated_at || doc.ts || "",
    content: doc.content,
  };
}

export function createDocsService({ api }) {
  return {
    normalizeDoc,
    async listDocs(projectId) {
      const payload = await api.request(`/projects/${encodeURIComponent(projectId)}/docs`);
      return (payload.docs || []).map(normalizeDoc);
    },
    async getDoc(projectId, nameOrId) {
      const payload = await api.request(
        `/projects/${encodeURIComponent(projectId)}/docs/content?path=${encodeURIComponent(nameOrId)}`
      );
      return {
        ...normalizeDoc({ path: nameOrId }),
        content: payload.content || "",
      };
    },
  };
}
