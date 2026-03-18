export async function runBootstrapInitialization({
  loadProjects,
  setProjectState,
  refreshUiPreferences,
  updateThinking,
  hydrateSelectedProject,
  resolveRouteFromHash,
  navigateToRoute,
  applyRoute,
  showToast,
  getProjectId,
  hasLocationHash,
}) {
  const warn = (label, error) => {
    const detail = error?.message || String(error || "未知錯誤");
    showToast?.(`${label}：${detail}`, 12000, "warning");
  };

  try {
    await loadProjects?.();
  } catch (error) {
    warn("載入專案清單失敗", error);
  }

  try {
    setProjectState?.(getProjectId?.());
  } catch (error) {
    warn("套用專案狀態失敗", error);
  }

  try {
    await refreshUiPreferences?.(getProjectId?.());
  } catch (error) {
    warn("載入 UI 設定失敗", error);
  }

  try {
    updateThinking?.({
      status: "idle",
      brief: "待命中；送出訊息後會顯示 Thinking、Plan 與工具事件",
    });
  } catch (error) {
    warn("初始化 Thinking 面板失敗", error);
  }

  try {
    await hydrateSelectedProject?.();
  } catch (error) {
    warn("同步專案上下文失敗", error);
  }

  try {
    const routeKey = resolveRouteFromHash?.() || "chat";
    if (hasLocationHash?.()) {
      await applyRoute?.(routeKey);
    } else {
      navigateToRoute?.(routeKey);
    }
  } catch (error) {
    warn("載入畫面失敗", error);
  }
}
