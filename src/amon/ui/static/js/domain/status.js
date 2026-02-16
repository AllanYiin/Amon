export function formatUnknownValue(value, fallback = "尚未取得資料") {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  if (!text || text === "--" || text.toLowerCase() === "unknown") {
    return fallback;
  }
  return text;
}

export function shortenId(value, front = 6, back = 4) {
  const text = String(value || "");
  if (!text) return "尚未有 Run";
  if (text.length <= front + back + 1) return text;
  return `${text.slice(0, front)}…${text.slice(-back)}`;
}

export function applyPillClass(element, level = "neutral") {
  if (!element) return;
  element.classList.remove("pill--success", "pill--warning", "pill--danger", "pill--neutral");
  element.classList.add(`pill--${level}`);
}

export function setStatusText(element, text, level = "neutral", tooltip = "") {
  if (!element) return;
  element.textContent = text;
  if (tooltip) element.title = tooltip;
  applyPillClass(element, level);
}

export function mapRunStatusLevel(status = "idle") {
  const key = String(status || "").toLowerCase();
  if (["ok", "success", "succeeded", "completed"].includes(key)) return "success";
  if (["error", "failed", "unavailable"].includes(key)) return "danger";
  if (["confirm_required", "warning", "degraded"].includes(key)) return "warning";
  return "neutral";
}

export function mapDaemonStatusLevel(status = "idle") {
  const key = String(status || "").toLowerCase();
  if (["connected", "healthy"].includes(key)) return "success";
  if (["reconnecting"].includes(key)) return "warning";
  if (["error", "unavailable", "disconnected"].includes(key)) return "danger";
  return "neutral";
}
