export function createInputBar({ formEl, inputEl, attachmentsEl, previewEl, sendButtonEl, cancelButtonEl, onSubmit }) {
  let selectedFiles = [];
  let busy = false;

  function syncActionState() {
    formEl.classList.toggle("is-busy", busy);
    inputEl.disabled = busy;
    attachmentsEl.disabled = busy;
    if (sendButtonEl) {
      sendButtonEl.hidden = busy;
      sendButtonEl.disabled = busy;
    }
    if (cancelButtonEl) {
      cancelButtonEl.hidden = !busy;
      cancelButtonEl.disabled = !busy;
    }
  }

  function renderAttachmentPreview(files = []) {
    previewEl.innerHTML = "";
    if (!files.length) return;
    files.forEach((file, index) => {
      const item = document.createElement("div");
      item.className = "attachment-item";

      const info = document.createElement("span");
      info.className = "attachment-info";
      info.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "attachment-item__remove";
      removeBtn.setAttribute("aria-label", `移除附件 ${file.name}`);
      removeBtn.textContent = "close";
      removeBtn.addEventListener("click", () => {
        selectedFiles = selectedFiles.filter((_, fileIndex) => fileIndex !== index);
        renderAttachmentPreview(selectedFiles);
      });

      item.appendChild(info);
      item.appendChild(removeBtn);
      previewEl.appendChild(item);
    });
  }

  function setDisabled(disabled) {
    busy = Boolean(disabled);
    syncActionState();
  }

  function bind() {
    const handlers = [];
    syncActionState();
    const onFormSubmit = (event) => {
      event.preventDefault();
      if (busy) return;
      const message = inputEl.value.trim();
      if (!message) return;
      const files = [...selectedFiles];
      inputEl.value = "";
      attachmentsEl.value = "";
      selectedFiles = [];
      renderAttachmentPreview([]);
      onSubmit(message, files);
    };
    formEl.addEventListener("submit", onFormSubmit);
    handlers.push(() => formEl.removeEventListener("submit", onFormSubmit));

    const onAttachChange = (event) => {
      const incomingFiles = Array.from(event.target.files || []);
      if (!incomingFiles.length) return;
      selectedFiles = [...selectedFiles, ...incomingFiles];
      attachmentsEl.value = "";
      renderAttachmentPreview(selectedFiles);
    };
    attachmentsEl.addEventListener("change", onAttachChange);
    handlers.push(() => attachmentsEl.removeEventListener("change", onAttachChange));

    const onInputKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        formEl.requestSubmit();
      }
    };
    inputEl.addEventListener("keydown", onInputKeyDown);
    handlers.push(() => inputEl.removeEventListener("keydown", onInputKeyDown));

    return () => handlers.forEach((fn) => fn());
  }

  return {
    bind,
    renderAttachmentPreview,
    setDisabled,
  };
}
