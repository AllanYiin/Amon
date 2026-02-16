const TYPE_CLASS = {
  success: "toast--success",
  warning: "toast--warning",
  danger: "toast--danger",
  info: "toast--info",
  neutral: "toast--neutral",
};

export function createToastManager(toastElement) {
  if (!toastElement) return { show() {} };
  return {
    show(message, options = {}) {
      const type = options.type || "info";
      const duration = Number.isFinite(options.duration) ? options.duration : 9000;
      toastElement.classList.remove(...Object.values(TYPE_CLASS));
      toastElement.classList.add(TYPE_CLASS[type] || TYPE_CLASS.info, "visible");
      toastElement.textContent = message;
      window.clearTimeout(toastElement._timer);
      toastElement._timer = window.setTimeout(() => toastElement.classList.remove("visible"), duration);
    },
  };
}
