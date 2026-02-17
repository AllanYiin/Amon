import { createSplitPane } from "./splitPane.js";
import { t } from "../i18n.js";

export function createInspectorLayout({ elements, store, storage, storageKeys }) {
  const { readStorage, writeStorage } = storage;
  let splitPane = null;

  function applyPanelWidth(width) {
    const clamped = Math.max(280, Math.min(520, Number(width) || 320));
    elements.chatLayout?.style.setProperty("--context-panel-width", `${clamped}px`);
    return clamped;
  }

  function render(snapshot = {}) {
    const layout = snapshot.layout || {};
    const inspector = layout.inspector || {};
    const collapsed = Boolean(inspector.collapsed);
    const width = applyPanelWidth(inspector.width);

    elements.uiShell?.classList.toggle("is-context-collapsed", collapsed);
    elements.toggleContextPanel?.setAttribute("aria-expanded", String(!collapsed));
    if (elements.toggleContextPanel) {
      elements.toggleContextPanel.textContent = collapsed ? t("topbar.toggleContext.expand") : t("topbar.toggleContext.collapse");
    }
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
        const isDrawerOpen = Boolean(elements.uiShell?.classList.toggle("is-context-drawer-open"));
        if (elements.toggleContextPanel) {
          elements.toggleContextPanel.setAttribute("aria-expanded", String(isDrawerOpen));
          elements.toggleContextPanel.textContent = isDrawerOpen ? t("topbar.toggleContext.collapse") : t("topbar.toggleContext.expand");
        }
      } else {
        updateInspector({ collapsed: !inspector.collapsed });
      }
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
