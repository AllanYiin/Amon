export function createBillingService({ api }) {
  return {
    async getBillingSummary(projectId) {
      const projectParam = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      return api.request(`/billing/summary${projectParam}`);
    },
    async getBillingSeries(projectId) {
      const projectParam = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
      const payload = await api.request(`/billing/series${projectParam}`);
      return payload.series || [];
    },
  };
}
