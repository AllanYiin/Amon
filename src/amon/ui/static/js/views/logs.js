export const LOGS_VIEW = {
  key: "logs-events",
  onEnter: async ({ loadLogsEventsPage }) => {
    await loadLogsEventsPage();
  },
};
