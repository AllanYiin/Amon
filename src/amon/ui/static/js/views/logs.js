/** @type {import('./contracts.js').ViewContract} */
export const LOGS_VIEW = {
  id: "logs-events",
  route: "/logs",
  mount(ctx) {
    this.__loadLogsEventsPage = async () => {
      await ctx.services.admin.loadLogsEventsPage();
    };
  },
  unmount() {
    this.__loadLogsEventsPage = null;
  },
  onRoute: async function () {
    await this.__loadLogsEventsPage?.();
  },
};
