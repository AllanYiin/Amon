/** @type {import('./contracts.js').ViewContract} */
export const LOGS_VIEW = {
  id: "logs-events",
  route: "/logs",
  mount: () => {},
  unmount: () => {},
  onRoute: async (_params = {}, ctx) => {
    await ctx.services?.admin?.loadLogsEventsPage?.();
  },
};
