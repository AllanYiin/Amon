export function createSidebarLayout({ elements, store }) {
  const shell = elements.uiShell;
  const navItems = Array.from(elements.shellNavItems || []);
  const toggleButton = elements.toggleSidebar;

  function focusByOffset(currentIndex, offset) {
    if (!navItems.length) return;
    const nextIndex = (currentIndex + offset + navItems.length) % navItems.length;
    navItems[nextIndex]?.focus();
  }

  function render(snapshot = {}) {
    const layout = snapshot.layout || {};
    const activeRoute = layout.activeRoute || "chat";
    const collapsed = Boolean(layout.sidebarCollapsed);
    shell?.classList.toggle("is-sidebar-collapsed", collapsed);
    if (toggleButton) {
      toggleButton.setAttribute("aria-expanded", String(!collapsed));
    }

    navItems.forEach((item) => {
      const isActive = item.dataset.route === activeRoute;
      item.classList.toggle("is-active", isActive);
      item.setAttribute("aria-current", isActive ? "page" : "false");
    });
  }

  function mount() {
    const unsubscribe = store.subscribe(render);
    render(store.getState());

    toggleButton?.addEventListener("click", () => {
      const current = store.getState().layout || {};
      store.patch({ layout: { ...current, sidebarCollapsed: !current.sidebarCollapsed } });
    });

    navItems.forEach((item, index) => {
      item.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          focusByOffset(index, 1);
        } else if (event.key === "ArrowUp") {
          event.preventDefault();
          focusByOffset(index, -1);
        } else if (event.key === "Home") {
          event.preventDefault();
          navItems[0]?.focus();
        } else if (event.key === "End") {
          event.preventDefault();
          navItems[navItems.length - 1]?.focus();
        }
      });
    });

    return () => unsubscribe();
  }

  return { mount, render };
}
