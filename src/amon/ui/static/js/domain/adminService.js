/**
 * @typedef {{ request: (path: string, options?: RequestInit & {quiet?: boolean}) => Promise<any> }} ApiClient
 */

/**
 * 建立 Admin Domain Service。
 * 僅負責呼叫後端與回傳資料，不處理 DOM 或 state。
 * @param {{api: ApiClient}} deps
 */
export function createAdminService({ api }) {
  return {
    /** @param {string} projectId */
    getConfigView(projectId) {
      const projectParam = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/config/view${projectParam}`);
    },
    /** @param {string} projectId */
    getBillingSummary(projectId) {
      const projectParam = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/billing/summary${projectParam}`);
    },
    /** @param {URLSearchParams} query */
    getLogs(query) {
      return api.request(`/logs/query?${query.toString()}`);
    },
    /** @param {URLSearchParams} query */
    getEvents(query) {
      return api.request(`/events/query?${query.toString()}`);
    },
    /** @param {string} projectId */
    getToolsCatalog(projectId) {
      const projectParam = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/tools/catalog${projectParam}`);
    },
    /** @param {string} projectId */
    getSkillsCatalog(projectId) {
      const projectParam = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/skills/catalog${projectParam}`);
    },
  };
}
