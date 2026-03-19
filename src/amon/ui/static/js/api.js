const DEFAULT_TIMEOUT_MS = 15000;
const FILE_PROTOCOL_HTTP_BASE =
  typeof window !== "undefined" && window.location?.protocol === "file:"
    ? String(window.__AMON_UI_HTTP_BASE__ || "http://127.0.0.1:8000").trim()
    : "";

function hasScheme(value) {
  return /^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(String(value || ""));
}

export function resolveAppUrl(url = "") {
  const rawUrl = String(url || "").trim();
  if (!rawUrl || !FILE_PROTOCOL_HTTP_BASE || hasScheme(rawUrl) || rawUrl.startsWith("//")) {
    return rawUrl;
  }
  const base = FILE_PROTOCOL_HTTP_BASE.replace(/\/+$/, "");
  if (rawUrl.startsWith("/")) {
    return `${base}${rawUrl}`;
  }
  return `${base}/${rawUrl.replace(/^\.?\//, "")}`;
}

export function resolveWsUrl(path = "") {
  const rawPath = String(path || "").trim();
  if (!rawPath) return rawPath;
  if (hasScheme(rawPath) || rawPath.startsWith("//")) return rawPath;
  if (FILE_PROTOCOL_HTTP_BASE) {
    const httpUrl = new URL(resolveAppUrl(rawPath));
    httpUrl.protocol = httpUrl.protocol === "https:" ? "wss:" : "ws:";
    return httpUrl.toString();
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${rawPath.startsWith("/") ? rawPath : `/${rawPath}`}`;
}

export async function requestJson(url, options = {}) {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const resolvedUrl = resolveAppUrl(url);
  try {
    const response = await fetch(resolvedUrl, {
      ...fetchOptions,
      headers: {
        "Content-Type": "application/json",
        ...(fetchOptions.headers || {}),
      },
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      throw new Error(`JSON 解析失敗：${resolvedUrl}`);
    }
    if (!response.ok) {
      throw new Error(payload.message || `HTTP ${response.status}`);
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`請求逾時（${timeoutMs}ms）：${resolvedUrl}`);
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}
