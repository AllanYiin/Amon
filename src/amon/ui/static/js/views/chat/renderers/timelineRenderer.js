export function createTimelineRenderer({ executionAccordion, executionTimeline, escapeHtml, shortenId, getRunId }) {
  function executionStatusMeta(status = "pending") {
    if (status === "succeeded") return { icon: "✅", label: "已完成" };
    if (status === "running") return { icon: "🔄", label: "執行中" };
    if (status === "failed") return { icon: "❌", label: "失敗" };
    return { icon: "⚪", label: "等待中" };
  }

  function renderExecutionTimeline() {
    if (!executionAccordion) return;
    const items = Array.from(executionTimeline.values());
    if (!items.length) {
      executionAccordion.innerHTML = '<p class="empty-context">尚無執行步驟。</p>';
      return;
    }
    executionAccordion.innerHTML = "";
    items.forEach((item) => {
      const statusMeta = executionStatusMeta(item.status);
      const details = document.createElement("details");
      details.className = `execution-step execution-step--${item.status}`;
      details.open = item.status === "running";
      details.innerHTML = `
        <summary>${statusMeta.icon} ${escapeHtml(item.title)} <span>${statusMeta.label}</span></summary>
        <div class="execution-step__body">
          <p>${escapeHtml(item.details || "尚無詳細資訊")}</p>
          <small>${item.inferred ? "推測來源（非結構化）" : "結構化事件"} · ${new Date(item.updatedAt).toLocaleTimeString("zh-TW", { hour12: false })}</small>
        </div>
      `;
      executionAccordion.appendChild(details);
    });
  }

  function updateExecutionStep(stepId, next = {}) {
    const current = executionTimeline.get(stepId) || {};
    executionTimeline.set(stepId, {
      id: stepId,
      title: next.title || current.title || stepId,
      status: next.status || current.status || "pending",
      details: next.details || current.details || "",
      inferred: next.inferred !== undefined ? next.inferred : current.inferred || false,
      updatedAt: new Date().toISOString(),
    });
    renderExecutionTimeline();
  }

  function applyExecutionEvent(eventType, data = {}) {
    if (eventType === "token") {
      updateExecutionStep("thinking", { title: "Thinking", status: "running", details: "模型正在輸出 token", inferred: false });
      return;
    }
    if (eventType === "plan") {
      updateExecutionStep("planning", { title: "Planning", status: "running", details: "已產生 Plan Card，等待確認", inferred: false });
      return;
    }
    if (eventType === "result") {
      updateExecutionStep("tool_execution", { title: "Tool execution", status: "succeeded", details: "工具呼叫已回傳結果", inferred: false });
      return;
    }
    if (eventType === "done") {
      updateExecutionStep("thinking", { title: "Thinking", status: "succeeded", details: `流程完成（${data.status || "ok"}）`, inferred: false });
      updateExecutionStep("planning", { title: "Planning", status: data.status === "confirm_required" ? "running" : "succeeded", details: data.status === "confirm_required" ? "等待使用者確認" : "規劃流程已完成", inferred: false });
      const runId = getRunId();
      updateExecutionStep("node_status", { title: "Node 狀態", status: data.status === "ok" ? "succeeded" : "running", details: runId ? `Run ${shortenId(runId)} 已更新` : "等待下一次 context refresh", inferred: true });
      return;
    }
    if (eventType === "error") {
      updateExecutionStep("tool_execution", { title: "Tool execution", status: "failed", details: data.message || "執行時發生錯誤", inferred: false });
    }
  }

  return {
    updateExecutionStep,
    applyExecutionEvent,
    renderExecutionTimeline,
  };
}
