import { t } from "../i18n.js";

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
    if (previousActive instanceof HTMLElement) previousActive.focus();
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
      titleElement && (titleElement.textContent = options.title || t("modal.confirm.title"));
      descriptionElement && (descriptionElement.textContent = options.description || t("modal.confirm.description"));
      confirmButton && (confirmButton.textContent = options.confirmText || t("modal.confirm.ok"));
      cancelButton && (cancelButton.textContent = options.cancelText || t("modal.confirm.cancel"));
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
