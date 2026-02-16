export const routeToShellView = {
  chat: "chat",
  context: "context",
  graph: "graph",
  tools: "tools-skills",
  config: "config",
  logs: "logs-events",
  docs: "docs",
  billing: "bill",
};

export function setActiveShellNav(elements, routeKey) {
  elements.shellNavItems.forEach((item) => {
    const isActive = item.dataset.route === routeKey;
    item.classList.toggle("is-active", isActive);
    item.setAttribute("aria-current", isActive ? "page" : "false");
  });
}

export function switchShellView({ view, state, elements, closeBillingStream }) {
  if (view !== "bill") {
    closeBillingStream();
  }
  state.shellView = view;
  elements.chatLayout.hidden = view !== "chat";
  elements.contextPage.hidden = view !== "context";
  elements.graphPage.hidden = view !== "graph";
  elements.toolsSkillsPage.hidden = view !== "tools-skills";
  elements.billPage.hidden = view !== "bill";
  elements.configPage.hidden = view !== "config";
  elements.logsEventsPage.hidden = view !== "logs-events";
  elements.docsPage.hidden = view !== "docs";
  if (view !== "chat") {
    elements.uiShell?.classList.remove("is-context-drawer-open");
  }
}
