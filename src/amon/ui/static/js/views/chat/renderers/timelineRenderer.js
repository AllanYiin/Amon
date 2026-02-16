import { t } from "../../../i18n.js";

export function createTimelineRenderer({ executionAccordion, executionTimeline, escapeHtml, shortenId, getRunId }) {
  function executionStatusMeta(status = "pending") {
    if (status === "succeeded") return { icon: "✅", label: t("timeline.status.succeeded") };
    if (status === "running") return { icon: "🔄", label: t("timeline.status.running") };
    if (status === "failed") return { icon: "❌", label: t("timeline.status.failed") };
    return { icon: "⚪", label: t("timeline.status.pending") };
  }

  function renderExecutionTimeline() {
    if (!executionAccordion) return;
    const items = Array.from(executionTimeline.values());
    if (!items.length) {
      executionAccordion.innerHTML = `<p class="empty-context">${t("timeline.empty")}</p>`;
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
          <p>${escapeHtml(item.details || t("timeline.noDetails"))}</p>
          <small>${item.inferred ? t("timeline.inferred") : t("timeline.structured")} · ${new Date(item.updatedAt).toLocaleTimeString("zh-TW", { hour12: false })}</small>
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
      updateExecutionStep("thinking", { title: t("timeline.step.thinking"), status: "running", details: t("timeline.tokenOutput"), inferred: false });
      return;
    }
    if (eventType === "plan") {
      updateExecutionStep("planning", { title: t("timeline.step.planning"), status: "running", details: t("timeline.planWaiting"), inferred: false });
      return;
    }
    if (eventType === "result") {
      updateExecutionStep("tool_execution", { title: t("timeline.step.toolExecution"), status: "succeeded", details: t("timeline.toolReturned"), inferred: false });
      return;
    }
    if (eventType === "done") {
      const status = data.status || "ok";
      updateExecutionStep("thinking", { title: t("timeline.step.thinking"), status: "succeeded", details: t("timeline.done", "", { status }), inferred: false });
      updateExecutionStep("planning", { title: t("timeline.step.planning"), status: status === "confirm_required" ? "running" : "succeeded", details: status === "confirm_required" ? t("timeline.waitingConfirm") : t("timeline.planDone"), inferred: false });
      const runId = getRunId();
      updateExecutionStep("node_status", { title: t("timeline.step.nodeStatus"), status: status === "ok" ? "succeeded" : "running", details: runId ? t("timeline.runUpdated", "", { runId: shortenId(runId) }) : t("timeline.waitingContextRefresh"), inferred: true });
      return;
    }
    if (eventType === "error") {
      updateExecutionStep("tool_execution", { title: t("timeline.step.toolExecution"), status: "failed", details: data.message || t("timeline.error"), inferred: false });
    }
  }

  return {
    updateExecutionStep,
    applyExecutionEvent,
    renderExecutionTimeline,
  };
}
