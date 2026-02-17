import { createSplitPane } from "./splitPane.js";
import { t } from "../i18n.js";

export function createInspectorLayout({ elements, store, storage, storageKeys, onTabChange }) {
  const { readStorage, writeStorage } = storage;
  let splitPane = null;

  function applyPanelWidth(width) {
    const clamped = Math.max(280, Math.min(520, Number(width) || 320));
    elements.chatLayout?.style.setProperty("--context-panel-width", `${clamped}px`);
    return clamped;
  }

  function renderTabs(activeTab = "thinking") {
    elements.contextTabs.forEach((tab) => {
      const isActive = tab.dataset.contextTab === activeTab;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", String(isActive));
      tab.setAttribute("tabindex", isActive ? "0" : "-1");
    });
    elements.contextPanels.forEach((panel) => {
      panel.hidden = panel.dataset.contextPanel !== activeTab;
    });
  }

  function render(snapshot = {}) {
    const layout = snapshot.layout || {};
    const inspector = layout.inspector || {};
    const collapsed = Boolean(inspector.collapsed);
    const activeTab = inspector.activeTab || "thinking";
    const width = applyPanelWidth(inspector.width);

    elements.uiShell?.classList.toggle("is-context-collapsed", collapsed);
    elements.toggleContextPanel?.setAttribute("aria-expanded", String(!collapsed));
    if (elements.toggleContextPanel) {
      elements.toggleContextPanel.textContent = collapsed ? t("topbar.toggleContext.expand") : t("topbar.toggleContext.collapse");
    }
    renderTabs(activeTab);

    writeStorage(storageKeys.contextCollapsed, collapsed ? "1" : "0");
    writeStorage(storageKeys.contextWidth, String(width));
  }

  function updateInspector(patch = {}) {
    const current = store.getState().layout || {};
    const currentInspector = current.inspector || {};
    store.patch({
      layout: {
        ...current,
        inspector: { ...currentInspector, ...patch },
      },
    });
  }

  function mount() {
    const collapsed = readStorage(storageKeys.contextCollapsed) === "1";
    const storedWidth = Number(readStorage(storageKeys.contextWidth));
    const width = Number.isFinite(storedWidth) && storedWidth > 0 ? storedWidth : 320;
    updateInspector({ collapsed, width });

    const unsubscribe = store.subscribe(render);
    render(store.getState());

    elements.toggleContextPanel?.addEventListener("click", () => {
      const inspector = (store.getState().layout || {}).inspector || {};
      if (window.innerWidth <= 1200) {
        elements.uiShell?.classList.toggle("is-context-drawer-open");
      } else {
        updateInspector({ collapsed: !inspector.collapsed });
      }
    });

    elements.contextTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const nextTab = tab.dataset.contextTab || "thinking";
        updateInspector({ activeTab: nextTab });
        if (typeof onTabChange === "function") onTabChange(nextTab);
      });

      tab.addEventListener("keydown", (event) => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
        const tabs = Array.from(elements.contextTabs || []);
        const currentIndex = tabs.indexOf(tab);
        if (currentIndex < 0) return;
        event.preventDefault();
        let nextIndex = currentIndex;
        if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
        if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") nextIndex = 0;
        if (event.key === "End") nextIndex = tabs.length - 1;
        const nextTab = tabs[nextIndex];
        nextTab?.focus();
        if (nextTab?.dataset.contextTab) {
          updateInspector({ activeTab: nextTab.dataset.contextTab });
          if (typeof onTabChange === "function") onTabChange(nextTab.dataset.contextTab);
        }
      });
    });

    splitPane = createSplitPane({
      handle: elements.contextResizer,
      container: elements.chatLayout,
      onResize: (nextWidth) => updateInspector({ width: nextWidth }),
    });

    return () => {
      unsubscribe();
      splitPane?.destroy();
    };
  }

  return { mount, render, updateInspector };
}
