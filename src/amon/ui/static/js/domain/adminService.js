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
    /** @param {{projectId?: string, enabled: boolean}} payload */
    setPlannerEnabled({ projectId, enabled }) {
      const scope = projectId ? "project" : "global";
      return this.setConfigValue({
        projectId,
        keyPath: "amon.planner.enabled",
        value: Boolean(enabled),
        scope,
      });
    },
    /** @param {{projectId?: string, keyPath: string, value: unknown, scope: 'global'|'project'}} payload */
    setConfigValue({ projectId, keyPath, value, scope }) {
      return api.request("/config/set", {
        method: "POST",
        body: JSON.stringify({
          key_path: keyPath,
          value,
          scope,
          project_id: projectId || "",
        }),
      });
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
    /** @param {{toolName: string, action: string, requireConfirm: boolean}} payload */
    planToolPolicy({ toolName, action, requireConfirm }) {
      return api.request("/tools/policy/plan", {
        method: "POST",
        body: JSON.stringify({ tool_name: toolName, action, require_confirm: requireConfirm }),
      });
    },
    /** @param {string} path @param {Record<string, unknown>} body */
    confirmPlan(path, body) {
      return api.request(path, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    /** @param {string} skillName @param {string} projectId */
    getSkillTriggerPreview(skillName, projectId) {
      return api.request("/skills/trigger-preview", {
        method: "POST",
        body: JSON.stringify({ skill_name: skillName, project_id: projectId || "" }),
      });
    },
  };
}
