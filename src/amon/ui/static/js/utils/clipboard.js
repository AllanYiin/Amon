export async function copyText(text, options = {}) {
  const value = String(text || "");
  const notify = typeof options.toast === "function" ? options.toast : () => {};

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      notify(options.successMessage || "已複製到剪貼簿", { type: "success" });
      return true;
    }
  } catch (_error) {
    // fallback below
  }

  try {
    const area = document.createElement("textarea");
    area.value = value;
    area.setAttribute("readonly", "readonly");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    if (!ok) throw new Error("execCommand copy failed");
    notify(options.successMessage || "已複製到剪貼簿", { type: "success" });
    return true;
  } catch (_error) {
    notify(options.errorMessage || "複製失敗，請手動複製", { type: "warning", duration: 10000 });
    return false;
  }
}
