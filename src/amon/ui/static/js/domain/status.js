import { daemonStatusPillLevelMap, runStatusPillLevelMap, statusI18nKeyMap, statusPillClassMap } from "../constants/status.js";
import { shortenId as shortenDisplayId } from "../utils/format.js";

export function formatUnknownValue(value, fallback = "尚未取得資料") {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  if (!text || text === "--" || text.toLowerCase() === "unknown") {
    return fallback;
  }
  return text;
}

export function shortenId(value, front = 6, back = 4) {
  const shortened = shortenDisplayId(value, front, back);
  return shortened === "--" ? "尚未有 Run" : shortened;
}

export function applyPillClass(element, level = "neutral") {
  if (!element) return;
  element.classList.remove("pill--success", "pill--warning", "pill--danger", "pill--neutral");
  element.classList.add(statusPillClassMap[level] || statusPillClassMap.neutral);
}

export function setStatusText(element, text, level = "neutral", tooltip = "") {
  if (!element) return;
  element.textContent = text;
  if (tooltip) element.title = tooltip;
  applyPillClass(element, level);
}

export function mapRunStatusLevel(status = "idle") {
  const key = String(status || "").toLowerCase();
  return runStatusPillLevelMap[key] || "neutral";
}

export function mapDaemonStatusLevel(status = "idle") {
  const key = String(status || "").toLowerCase();
  return daemonStatusPillLevelMap[key] || "neutral";
}

export function statusToI18nKey(domain, status, fallbackKey) {
  const namespace = statusI18nKeyMap[domain] || {};
  return namespace[String(status || "").toLowerCase()] || fallbackKey;
}
