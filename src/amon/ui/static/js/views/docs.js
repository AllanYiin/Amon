export const DOCS_VIEW = {
  key: "docs",
  onEnter: async ({ loadDocsPage }) => {
    await loadDocsPage();
  },
};
