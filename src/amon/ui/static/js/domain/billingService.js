export function createBillingService({ api }) {
  function requireProjectId(projectId) {
    const normalized = String(projectId || "").trim();
    if (!normalized) {
      throw new Error("目前尚未選擇專案，無法載入 Billing。請先建立或選擇專案。");
    }
    return normalized;
  }

  return {
    async getBillingSummary(projectId) {
      const normalized = requireProjectId(projectId);
      const projectParam = `?project_id=${encodeURIComponent(normalized)}`;
      return api.request(`/billing/summary${projectParam}`);
    },
    async getBillingSeries(projectId) {
      const normalized = requireProjectId(projectId);
      const projectParam = `?project_id=${encodeURIComponent(normalized)}`;
      const payload = await api.request(`/billing/series${projectParam}`);
      return payload.series || [];
    },
  };
}
