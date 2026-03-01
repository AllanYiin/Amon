export function createContextService({ api }) {
  return {
    async getContext(projectId, chatId = "") {
      const query = String(chatId || "").trim()
        ? `?chat_id=${encodeURIComponent(String(chatId).trim())}`
        : "";
      return api.request(`/projects/${encodeURIComponent(projectId)}/context${query}`);
    },
    async getContextStats(projectId, chatId = "") {
      const query = String(chatId || "").trim()
        ? `?chat_id=${encodeURIComponent(String(chatId).trim())}`
        : "";
      return api.request(`/projects/${encodeURIComponent(projectId)}/context/stats${query}`);
    },
    async saveContext(projectId, contextText) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/context`, {
        method: "PUT",
        body: JSON.stringify({ context: contextText }),
      });
    },
    async clearContext(scope = "project", options = {}) {
      const projectId = String(options?.projectId || "").trim();
      const chatId = String(options?.chatId || "").trim();
      return api.request("/context/clear", {
        method: "POST",
        body: JSON.stringify({ scope, project_id: projectId, chat_id: chatId || null }),
      });
    },
  };
}
