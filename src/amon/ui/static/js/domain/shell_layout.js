export function createShellLayoutController({ elements, state, storage, storageKeys }) {
  const { readStorage, writeStorage } = storage;

  function syncContextPanelToggle() {
    if (!elements.uiShell || !elements.toggleContextPanel) return;
    const collapsed = elements.uiShell.classList.contains("is-context-collapsed");
    elements.toggleContextPanel.textContent = collapsed ? "展開右側面板" : "收合右側面板";
    elements.toggleContextPanel.setAttribute("aria-expanded", String(!collapsed));
    writeStorage(storageKeys.contextCollapsed, collapsed ? "1" : "0");
  }

  function applyContextPanelWidth(width) {
    const clamped = Math.max(280, Math.min(520, Number(width) || 320));
    state.contextPanelWidth = clamped;
    elements.chatLayout?.style.setProperty("--context-panel-width", `${clamped}px`);
    writeStorage(storageKeys.contextWidth, String(clamped));
  }

  function restoreContextPanelState() {
    const collapsed = readStorage(storageKeys.contextCollapsed) === "1";
    elements.uiShell?.classList.toggle("is-context-collapsed", collapsed);
    const storedWidth = Number(readStorage(storageKeys.contextWidth));
    applyContextPanelWidth(Number.isFinite(storedWidth) && storedWidth > 0 ? storedWidth : 320);
    syncContextPanelToggle();
  }

  function setupContextResizer() {
    if (!elements.contextResizer || !elements.chatLayout || !elements.contextPanel) return;
    let dragging = false;
    const onMove = (event) => {
      if (!dragging) return;
      const layoutRect = elements.chatLayout.getBoundingClientRect();
      const width = layoutRect.right - event.clientX;
      applyContextPanelWidth(width);
    };
    const onUp = () => {
      dragging = false;
      document.body.classList.remove("is-resizing-context-panel");
    };
    elements.contextResizer.addEventListener("mousedown", (event) => {
      event.preventDefault();
      dragging = true;
      document.body.classList.add("is-resizing-context-panel");
    });
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  function bindToggles() {
    elements.toggleContextPanel?.addEventListener("click", () => {
      if (window.innerWidth <= 1200) {
        elements.uiShell?.classList.toggle("is-context-drawer-open");
      } else {
        elements.uiShell?.classList.toggle("is-context-collapsed");
      }
      syncContextPanelToggle();
    });

    elements.toggleSidebar?.addEventListener("click", () => {
      elements.uiShell?.classList.toggle("is-sidebar-collapsed");
    });
  }

  return {
    syncContextPanelToggle,
    applyContextPanelWidth,
    restoreContextPanelState,
    setupContextResizer,
    bindToggles,
  };
}
