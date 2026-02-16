(function initAmonUiComponents(globalScope) {
  const TYPE_CLASS = {
    success: "toast--success",
    warning: "toast--warning",
    danger: "toast--danger",
    info: "toast--info",
    neutral: "toast--neutral",
  };

  function createToastManager(toastElement) {
    if (!toastElement) {
      return {
        show() {},
      };
    }

    return {
      show(message, options = {}) {
        const type = options.type || "info";
        const duration = Number.isFinite(options.duration) ? options.duration : 9000;
        toastElement.classList.remove(...Object.values(TYPE_CLASS));
        toastElement.classList.add(TYPE_CLASS[type] || TYPE_CLASS.info);
        toastElement.textContent = message;
        toastElement.classList.add("visible");
        window.clearTimeout(toastElement._timer);
        toastElement._timer = window.setTimeout(() => {
          toastElement.classList.remove("visible");
        }, duration);
      },
    };
  }

  function createConfirmModal(modalElement) {
    if (!modalElement) {
      return {
        open() {
          return Promise.resolve(false);
        },
        close() {},
      };
    }

    const titleElement = modalElement.querySelector("[data-confirm-title]");
    const descriptionElement = modalElement.querySelector("[data-confirm-description]");
    const cancelButton = modalElement.querySelector("[data-confirm-cancel]");
    const confirmButton = modalElement.querySelector("[data-confirm-ok]");

    let resolver = null;

    function close(result) {
      modalElement.hidden = true;
      modalElement.setAttribute("aria-hidden", "true");
      if (resolver) {
        resolver(Boolean(result));
        resolver = null;
      }
    }

    cancelButton?.addEventListener("click", () => close(false));
    confirmButton?.addEventListener("click", () => close(true));

    modalElement.addEventListener("click", (event) => {
      if (event.target === modalElement) {
        close(false);
      }
    });

    modalElement.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        close(false);
      }
    });

    return {
      open(options = {}) {
        if (titleElement) {
          titleElement.textContent = options.title || "請再次確認";
        }
        if (descriptionElement) {
          descriptionElement.textContent = options.description || "這個動作無法復原，是否繼續？";
        }
        if (confirmButton) {
          confirmButton.textContent = options.confirmText || "確認";
        }
        if (cancelButton) {
          cancelButton.textContent = options.cancelText || "取消";
        }

        modalElement.hidden = false;
        modalElement.setAttribute("aria-hidden", "false");
        confirmButton?.focus();

        if (resolver) {
          resolver(false);
        }

        return new Promise((resolve) => {
          resolver = resolve;
        });
      },
      close,
    };
  }

  globalScope.AmonUIComponents = {
    createToastManager,
    createConfirmModal,
  };
})(window);
