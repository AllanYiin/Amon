const TRUE_VALUES = new Set(["1", "true", "yes", "on", "debug"]);

function normalizeFlag(value) {
  return String(value || "").trim().toLowerCase();
}

export function isUiDebugEnabled() {
  if (typeof window === "undefined") return false;
  const queryFlag = new URLSearchParams(window.location.search || "").get("ui_debug");
  if (TRUE_VALUES.has(normalizeFlag(queryFlag))) return true;
  const localFlag = window.localStorage?.getItem("amon.ui.debug");
  return TRUE_VALUES.has(normalizeFlag(localFlag));
}

export function logViewInitDebug(viewId, payload = {}) {
  if (!isUiDebugEnabled()) return;
  console.debug(`[amon-ui-debug][${viewId}] init`, payload);
}
