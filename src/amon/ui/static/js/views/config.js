export const CONFIG_VIEW = {
  key: "config",
  onEnter: async ({ loadConfigPage }) => {
    await loadConfigPage();
  },
};
