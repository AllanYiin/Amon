/** @type {import('./contracts.js').ViewContract} */
export const CONFIG_VIEW = {
  id: "config",
  route: "/config",
  mount: () => {},
  unmount: () => {},
  onRoute: async (_params = {}, ctx) => {
    await ctx.services?.admin?.loadConfigPage?.();
  },
};
