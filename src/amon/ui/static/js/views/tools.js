/** @type {import('./contracts.js').ViewContract} */
export const TOOLS_VIEW = {
  id: "tools-skills",
  route: "/tools",
  mount: () => {},
  unmount: () => {},
  onRoute: async (_params = {}, ctx) => {
    await ctx.services?.admin?.loadToolsSkillsPage?.();
  },
};
