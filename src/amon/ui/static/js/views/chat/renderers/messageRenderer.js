import { t } from "../../../i18n.js";

export function createMessageRenderer({ timelineEl, renderMarkdown }) {
  const state = {
    pendingAssistantBubble: null,
  };

  function appendMessage(role, text, meta = {}) {
    const row = document.createElement("article");
    row.className = `timeline-row timeline-row--${role}`;

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;
    bubble.innerHTML = renderMarkdown(text);

    const footer = document.createElement("footer");
    footer.className = "timeline-meta";
    const roleLabel = role === "user" ? t("chat.role.user") : t("chat.role.agent");
    const status = meta.status ? `・${meta.status}` : "";
    footer.textContent = `${new Date().toLocaleTimeString("zh-TW", { hour12: false })}・${roleLabel}${status}`;

    row.appendChild(bubble);
    row.appendChild(footer);
    timelineEl.appendChild(row);
    timelineEl.scrollTop = timelineEl.scrollHeight;
    return bubble;
  }

  function appendTimelineStatus(message) {
    const item = document.createElement("div");
    item.className = "timeline-status timeline-status--event";
    item.textContent = message;
    timelineEl.appendChild(item);
    timelineEl.scrollTop = timelineEl.scrollHeight;
  }

  function applyTokenChunk(text = "") {
    if (!state.pendingAssistantBubble) {
      state.pendingAssistantBubble = appendMessage("agent", `${t("chat.role.agent")}：`, { status: t("chat.status.streaming") });
      state.pendingAssistantBubble.dataset.buffer = "";
    }
    state.pendingAssistantBubble.dataset.buffer = `${state.pendingAssistantBubble.dataset.buffer || ""}${text}`;
    state.pendingAssistantBubble.innerHTML = renderMarkdown(`${t("chat.role.agent")}：${state.pendingAssistantBubble.dataset.buffer}`);
    timelineEl.scrollTop = timelineEl.scrollHeight;
  }

  function finalizeAssistantBubble() {
    state.pendingAssistantBubble = null;
  }

  function reset() {
    state.pendingAssistantBubble = null;
  }

  return {
    appendMessage,
    appendTimelineStatus,
    applyTokenChunk,
    finalizeAssistantBubble,
    reset,
  };
}
