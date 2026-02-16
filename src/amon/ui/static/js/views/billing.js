/** @type {import('./contracts.js').ViewContract} */
export const BILLING_VIEW = {
  id: "bill",
  route: "/billing",
  mount: () => {},
  unmount: () => {},
  onRoute: async (_params = {}, ctx) => {
    await ctx.services?.admin?.loadBillPage?.();
  },
};
