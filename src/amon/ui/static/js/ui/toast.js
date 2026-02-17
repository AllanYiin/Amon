const TYPE_CLASS = {
  success: "toast--success",
  warning: "toast--warning",
  danger: "toast--danger",
  info: "toast--info",
  neutral: "toast--neutral",
};

export function createToastManager(toastElement, options = {}) {
  if (!toastElement) return { show() {} };
  const onShow = typeof options.onShow === "function" ? options.onShow : null;
  return {
    show(message, options = {}) {
      const type = options.type || "info";
      const normalizedMessage = typeof message === "string" ? message : String(message ?? "");
      const requestedDuration = Number.isFinite(options.duration) ? options.duration : 12000;
      const duration = Math.max(12000, requestedDuration);
      toastElement.classList.remove(...Object.values(TYPE_CLASS));
      toastElement.classList.add(TYPE_CLASS[type] || TYPE_CLASS.info, "visible");
      toastElement.textContent = normalizedMessage;
      window.clearTimeout(toastElement._timer);
      toastElement._timer = window.setTimeout(() => toastElement.classList.remove("visible"), duration);
      if (onShow) {
        onShow({
          type,
          duration,
          message: normalizedMessage,
          source: options.source || "ui",
          metadata: options.metadata || {},
        });
      }
    },
  };
}
