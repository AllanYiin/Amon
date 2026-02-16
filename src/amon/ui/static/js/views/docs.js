/** @type {import('./contracts.js').ViewContract} */
export const DOCS_VIEW = {
  id: "docs",
  route: "/docs",
  mount: () => {},
  unmount: () => {},
  onRoute: async (_params = {}, ctx) => {
    await ctx.services?.admin?.loadDocsPage?.();
  },
};
