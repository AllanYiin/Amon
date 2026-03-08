export function createContextService({ api }) {
  function threadContextPath(projectId, threadId = "") {
    const normalizedThreadId = String(threadId || "").trim();
    if (!normalizedThreadId) {
      return `/projects/${encodeURIComponent(projectId)}/context`;
    }
    return `/projects/${encodeURIComponent(projectId)}/threads/${encodeURIComponent(normalizedThreadId)}/context`;
  }

  function threadContextStatsPath(projectId, threadId = "") {
    const normalizedThreadId = String(threadId || "").trim();
    if (!normalizedThreadId) {
      return `/projects/${encodeURIComponent(projectId)}/context/stats`;
    }
    return `/projects/${encodeURIComponent(projectId)}/threads/${encodeURIComponent(normalizedThreadId)}/context/stats`;
  }

  return {
    async getContext(projectId, threadId = "") {
      return api.request(threadContextPath(projectId, threadId));
    },
    async getContextStats(projectId, threadId = "") {
      return api.request(threadContextStatsPath(projectId, threadId));
    },
    async saveContext(projectId, contextText) {
      return api.request(`/projects/${encodeURIComponent(projectId)}/context`, {
        method: "PUT",
        body: JSON.stringify({ context: contextText }),
      });
    },
    async clearContext(scope = "project", options = {}) {
      const projectId = String(options?.projectId || "").trim();
      const threadId = String(options?.threadId || options?.chatId || "").trim();
      return api.request("/context/clear", {
        method: "POST",
        body: JSON.stringify({ scope, project_id: projectId, chat_id: threadId || null }),
      });
    },
  };
}
