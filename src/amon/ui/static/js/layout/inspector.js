import { createSplitPane } from "./splitPane.js";
import { t } from "../i18n.js";

const INSPECTOR_TAB_IDS = ["artifacts", "execution", "thinking"];

export function createInspectorLayout({ elements, store, storage, storageKeys }) {
  const { readStorage, writeStorage } = storage;
  let splitPane = null;

  function applyPanelWidth(width) {
    const clamped = Math.max(280, Math.min(520, Number(width) || 320));
    elements.chatLayout?.style.setProperty("--context-panel-width", `${clamped}px`);
    return clamped;
  }

  function normalizeActiveTab(tab) {
    return INSPECTOR_TAB_IDS.includes(tab) ? tab : "artifacts";
  }

  function applyInspectorTabs(activeTab) {
    const normalizedTab = normalizeActiveTab(activeTab);
    const sectionMap = {
      thinking: elements.inspectorThinking,
      artifacts: elements.inspectorArtifacts,
      execution: elements.inspectorExecution,
    };

    for (const tabId of INSPECTOR_TAB_IDS) {
      const section = sectionMap[tabId];
      if (!section) continue;
      section.hidden = tabId !== normalizedTab;
    }

    elements.inspectorTabButtons?.forEach((button) => {
      const tabId = button.dataset.inspectorTab;
      const isActive = tabId === normalizedTab;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", String(isActive));
      button.tabIndex = isActive ? 0 : -1;
    });
  }

  function render(snapshot = {}) {
    const layout = snapshot.layout || {};
    const inspector = layout.inspector || {};
    const collapsed = Boolean(inspector.collapsed);
    const width = applyPanelWidth(inspector.width);
    const activeTab = normalizeActiveTab(inspector.activeTab);

    elements.uiShell?.classList.toggle("is-context-collapsed", collapsed);
    elements.toggleContextPanel?.setAttribute("aria-expanded", String(!collapsed));
    if (elements.toggleContextPanel) {
      elements.toggleContextPanel.textContent = collapsed ? t("topbar.toggleContext.expand") : t("topbar.toggleContext.collapse");
    }

    applyInspectorTabs(activeTab);

    writeStorage(storageKeys.contextCollapsed, collapsed ? "1" : "0");
    writeStorage(storageKeys.contextWidth, String(width));
  }

  function updateInspector(patch = {}) {
    const current = store.getState().layout || {};
    const currentInspector = current.inspector || {};
    const nextPatch = { ...patch };
    if ("activeTab" in nextPatch) {
      nextPatch.activeTab = normalizeActiveTab(nextPatch.activeTab);
    }
    store.patch({
      layout: {
        ...current,
        inspector: { ...currentInspector, ...nextPatch },
      },
    });
  }

  function focusActiveTab() {
    const activeButton = Array.from(elements.inspectorTabButtons || []).find((button) => button.getAttribute("aria-selected") === "true");
    activeButton?.focus();
  }

  function mount() {
    const collapsed = readStorage(storageKeys.contextCollapsed) === "1";
    const storedWidth = Number(readStorage(storageKeys.contextWidth));
    const width = Number.isFinite(storedWidth) && storedWidth > 0 ? storedWidth : 320;
    updateInspector({ collapsed, width, activeTab: "artifacts" });

    const unsubscribe = store.subscribe(render);
    render(store.getState());

    elements.inspectorTabButtons?.forEach((button) => {
      button.addEventListener("click", () => {
        updateInspector({ activeTab: button.dataset.inspectorTab });
      });
      button.addEventListener("keydown", (event) => {
        const currentTab = button.dataset.inspectorTab;
        const currentIndex = INSPECTOR_TAB_IDS.indexOf(currentTab);
        if (currentIndex < 0) return;

        let targetIndex = -1;
        if (event.key === "ArrowRight") targetIndex = (currentIndex + 1) % INSPECTOR_TAB_IDS.length;
        if (event.key === "ArrowLeft") targetIndex = (currentIndex - 1 + INSPECTOR_TAB_IDS.length) % INSPECTOR_TAB_IDS.length;
        if (event.key === "Home") targetIndex = 0;
        if (event.key === "End") targetIndex = INSPECTOR_TAB_IDS.length - 1;
        if (targetIndex < 0) return;

        event.preventDefault();
        updateInspector({ activeTab: INSPECTOR_TAB_IDS[targetIndex] });
        requestAnimationFrame(focusActiveTab);
      });
    });

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

  return { mount, render, updateInspector, normalizeActiveTab };
}
