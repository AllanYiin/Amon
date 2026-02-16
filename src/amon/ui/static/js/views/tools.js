export const TOOLS_VIEW = {
  key: "tools-skills",
  onEnter: async ({ loadToolsSkillsPage }) => {
    await loadToolsSkillsPage();
  },
};
