export function formatBytes(bytes, decimals = 1) {
  const value = Number(bytes);
  if (!Number.isFinite(value) || value < 0) return "--";
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const normalized = value / 1024 ** index;
  return `${normalized.toFixed(decimals)} ${units[index]}`;
}

export function formatDateTime(input, locale = "zh-TW") {
  if (!input) return "--";
  const date = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(date.getTime())) return "--";
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function shortenId(value, front = 6, back = 4) {
  const text = String(value || "");
  if (!text) return "--";
  if (text.length <= front + back + 1) return text;
  return `${text.slice(0, front)}…${text.slice(-back)}`;
}

export function safeJsonStringify(payload, fallback = "") {
  try {
    return JSON.stringify(payload, null, 2);
  } catch (_error) {
    return fallback;
  }
}
