export const VIRTUAL_PROJECT_ID = "__virtual__";

export function isVirtualProjectId(projectId) {
  return String(projectId || "").trim() === VIRTUAL_PROJECT_ID;
}

export function normalizeProjectIdForUi(projectId) {
  const normalized = String(projectId || "").trim();
  if (!normalized || normalized === VIRTUAL_PROJECT_ID) {
    return "";
  }
  return normalized;
}

export function hasConcreteProjectId(projectId) {
  return normalizeProjectIdForUi(projectId) !== "";
}
