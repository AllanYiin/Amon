export function createConfirmModal(modalElement) {
  if (!modalElement) return { open: async () => false, close() {} };
  const panel = modalElement.querySelector(".confirm-modal__panel");
  const titleElement = modalElement.querySelector("[data-confirm-title]");
  const descriptionElement = modalElement.querySelector("[data-confirm-description]");
  const cancelButton = modalElement.querySelector("[data-confirm-cancel]");
  const confirmButton = modalElement.querySelector("[data-confirm-ok]");
  const focusableSelector = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";
  let resolver = null;
  let previousActive = null;

  function trapFocus(event) {
    if (event.key !== "Tab") return;
    const nodes = panel ? [...panel.querySelectorAll(focusableSelector)].filter((n) => !n.disabled) : [];
    if (!nodes.length) return;
    const first = nodes[0];
    const last = nodes[nodes.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function close(result) {
    modalElement.hidden = true;
    modalElement.setAttribute("aria-hidden", "true");
    modalElement.removeEventListener("keydown", trapFocus);
    if (previousActive) previousActive.focus();
    if (resolver) {
      resolver(Boolean(result));
      resolver = null;
    }
  }

  cancelButton?.addEventListener("click", () => close(false));
  confirmButton?.addEventListener("click", () => close(true));
  modalElement.addEventListener("click", (event) => event.target === modalElement && close(false));
  modalElement.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close(false);
  });

  return {
    open(options = {}) {
      titleElement && (titleElement.textContent = options.title || "請再次確認");
      descriptionElement && (descriptionElement.textContent = options.description || "此操作無法復原，是否繼續？");
      confirmButton && (confirmButton.textContent = options.confirmText || "確認");
      cancelButton && (cancelButton.textContent = options.cancelText || "取消");
      previousActive = document.activeElement;
      modalElement.hidden = false;
      modalElement.setAttribute("aria-hidden", "false");
      modalElement.addEventListener("keydown", trapFocus);
      confirmButton?.focus();
      return new Promise((resolve) => {
        resolver = resolve;
      });
    },
    close,
  };
}
