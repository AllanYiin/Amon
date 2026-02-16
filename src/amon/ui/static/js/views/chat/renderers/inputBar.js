export function createInputBar({ formEl, inputEl, attachmentsEl, previewEl, onSubmit }) {
  function renderAttachmentPreview(files = []) {
    previewEl.innerHTML = "";
    if (!files.length) return;
    files.forEach((file) => {
      const item = document.createElement("div");
      item.className = "attachment-item";
      const info = document.createElement("div");
      info.className = "attachment-info";
      info.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;

      if (file.type.startsWith("image/")) {
        const img = document.createElement("img");
        img.alt = file.name;
        img.src = URL.createObjectURL(file);
        img.onload = () => URL.revokeObjectURL(img.src);
        item.appendChild(img);
      } else if (file.type.startsWith("video/")) {
        const video = document.createElement("video");
        video.src = URL.createObjectURL(file);
        video.controls = true;
        video.onloadeddata = () => URL.revokeObjectURL(video.src);
        item.appendChild(video);
      } else if (file.type === "application/pdf") {
        const embed = document.createElement("embed");
        embed.src = URL.createObjectURL(file);
        embed.type = "application/pdf";
        embed.onload = () => URL.revokeObjectURL(embed.src);
        item.appendChild(embed);
      }
      item.appendChild(info);
      previewEl.appendChild(item);
    });
  }

  function setDisabled(disabled) {
    inputEl.disabled = disabled;
  }

  function bind() {
    const handlers = [];
    const onFormSubmit = (event) => {
      event.preventDefault();
      const message = inputEl.value.trim();
      if (!message) return;
      const files = Array.from(attachmentsEl.files || []);
      inputEl.value = "";
      attachmentsEl.value = "";
      renderAttachmentPreview([]);
      onSubmit(message, files);
    };
    formEl.addEventListener("submit", onFormSubmit);
    handlers.push(() => formEl.removeEventListener("submit", onFormSubmit));

    const onAttachChange = (event) => {
      renderAttachmentPreview(Array.from(event.target.files || []));
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
