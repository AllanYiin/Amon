export const BILLING_VIEW = {
  key: "bill",
  onEnter: async ({ loadBillPage }) => {
    await loadBillPage();
  },
};
