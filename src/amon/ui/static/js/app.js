import { bootstrapApp } from "./bootstrap.js";

function renderBootstrapFailure(error) {
  console.error("ui_bootstrap_failed", error);

  const daemonPill = document.getElementById("shell-daemon-status");
  if (daemonPill) {
    daemonPill.textContent = "啟動失敗";
    daemonPill.title = `前端初始化失敗：${error?.message || error || "未知錯誤"}`;
    daemonPill.classList.remove("pill--neutral", "pill--success", "pill--warning");
    daemonPill.classList.add("pill--danger");
  }

  const timeline = document.getElementById("timeline");
  if (timeline && !timeline.querySelector("[data-bootstrap-error='true']")) {
    const row = document.createElement("article");
    row.dataset.bootstrapError = "true";
    row.className = "timeline-status timeline-status--error";
    row.textContent = `UI 啟動失敗：${error?.message || error || "未知錯誤"}。請先檢查瀏覽器 console 與載入的前端資源。`;
    timeline.appendChild(row);
  }
}

try {
  bootstrapApp();
} catch (error) {
  renderBootstrapFailure(error);
}
