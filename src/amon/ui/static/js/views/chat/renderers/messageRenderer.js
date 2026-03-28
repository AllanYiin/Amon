import { t } from "../../../i18n.js";

export function createMessageRenderer({ timelineEl, renderMarkdown }) {
  const state = {
    pendingAssistantMessages: new Map(),
    latestPendingKey: "assistant:default",
  };

  function stickToBottom() {
    if (!timelineEl) return;
    window.requestAnimationFrame(() => {
      timelineEl.scrollTop = timelineEl.scrollHeight;
    });
  }

  function createArtifactPreview({ filename, previewText, onOpen }) {
    if (!filename && !previewText) return null;
    const card = document.createElement("section");
    card.className = "chat-artifact-card";

    const header = document.createElement("header");
    header.className = "chat-artifact-card__header";

    const title = document.createElement("span");
    title.className = "chat-artifact-card__title";
    title.textContent = filename || "未命名 Artifact";

    header.appendChild(title);

    if (typeof onOpen === "function") {
      const openButton = document.createElement("button");
      openButton.type = "button";
      openButton.className = "chat-artifact-card__open";
      openButton.textContent = "Open";
      openButton.addEventListener("click", () => onOpen());
      header.appendChild(openButton);
    }

    const body = document.createElement("pre");
    body.className = "chat-artifact-card__body";
    body.textContent = previewText || "";

    card.appendChild(header);
    card.appendChild(body);
    return card;
  }

  function appendMessage(role, text, meta = {}) {
    const message = document.createElement("article");
    message.className = `chat-msg chat-msg--${role}`;

    let headerStatusEl = null;
    if (role === "agent") {
      const header = document.createElement("header");
      header.className = "chat-msg__header";

      const identity = document.createElement("div");
      identity.className = "chat-msg__identity";

      const avatar = document.createElement("span");
      avatar.className = "chat-msg__avatar";
      avatar.textContent = "A";

      const name = document.createElement("span");
      name.className = "chat-msg__name";
      name.textContent = t("chat.role.agent");

      identity.appendChild(avatar);
      identity.appendChild(name);
      header.appendChild(identity);

      headerStatusEl = document.createElement("span");
      headerStatusEl.className = "chat-msg__status";
      if (meta.status) {
        headerStatusEl.textContent = meta.status;
      } else {
        headerStatusEl.hidden = true;
      }
      header.appendChild(headerStatusEl);
      message.appendChild(header);
    }

    const bubble = document.createElement("div");
    bubble.className = `chat-msg__bubble chat-msg__bubble--${role}`;

    if (role === "agent" && meta.label) {
      const label = document.createElement("div");
      label.className = "chat-msg__node-label";
      label.textContent = meta.label;
      bubble.appendChild(label);
    }

    const bubbleBody = document.createElement("div");
    bubbleBody.className = "chat-msg__body";
    bubbleBody.innerHTML = renderMarkdown(text || "");
    bubble.appendChild(bubbleBody);

    if (meta.typing) {
      bubble.classList.add("is-typing");
    }

    if (meta.artifact) {
      const artifactPreview = createArtifactPreview(meta.artifact);
      if (artifactPreview) bubble.appendChild(artifactPreview);
    }

    message.appendChild(bubble);

    const footer = document.createElement("footer");
    footer.className = "chat-msg__meta";
    const timestamp = document.createElement("time");
    timestamp.className = "chat-msg__timestamp";
    const timestampText = String(meta.timestampText || "").trim();
    timestamp.textContent = timestampText || new Date().toLocaleTimeString("zh-TW", { hour12: false });
    footer.appendChild(timestamp);

    const footerStatusEl = document.createElement("span");
    footerStatusEl.className = "chat-msg__meta-status";
    if (meta.status) {
      footerStatusEl.textContent = meta.status;
      footer.appendChild(footerStatusEl);
    }

    message.appendChild(footer);

    timelineEl.appendChild(message);
    stickToBottom();
    return { message, bubble, bubbleBody, headerStatusEl, footerStatusEl };
  }

  function appendTimelineStatus(message) {
    const item = document.createElement("div");
    item.className = "timeline-status";
    item.textContent = message;
    timelineEl.appendChild(item);
    stickToBottom();
  }

  function pendingKeyForMeta(meta = {}) {
    const nodeId = String(meta.nodeId || "").trim();
    if (nodeId) return `assistant:${nodeId}`;
    return "assistant:default";
  }

  function nodeLabelForMeta(meta = {}) {
    const nodeTitle = String(meta.nodeTitle || "").trim();
    if (nodeTitle) return `節點：${nodeTitle}`;
    const nodeId = String(meta.nodeId || "").trim();
    if (nodeId) return `節點：${nodeId}`;
    return "";
  }

  function getOrCreatePendingAssistantMessage(meta = {}) {
    const key = pendingKeyForMeta(meta);
    state.latestPendingKey = key;
    if (!state.pendingAssistantMessages.has(key)) {
      const pendingAssistantMessage = appendMessage("agent", "", {
        status: t("chat.status.streaming"),
        typing: true,
        label: nodeLabelForMeta(meta),
      });
      pendingAssistantMessage.bubble.dataset.buffer = "";
      state.pendingAssistantMessages.set(key, pendingAssistantMessage);
    }
    return state.pendingAssistantMessages.get(key);
  }

  function applyTokenChunk(text = "", meta = {}) {
    const pendingAssistantMessage = getOrCreatePendingAssistantMessage(meta);
    pendingAssistantMessage.bubble.dataset.buffer = `${pendingAssistantMessage.bubble.dataset.buffer || ""}${text}`;
    pendingAssistantMessage.bubble.classList.remove("is-typing");
    pendingAssistantMessage.bubbleBody.innerHTML = renderMarkdown(pendingAssistantMessage.bubble.dataset.buffer);
    stickToBottom();
  }

  function getPendingBuffer() {
    const pendingAssistantMessage = state.pendingAssistantMessages.get(state.latestPendingKey);
    if (!pendingAssistantMessage) return "";
    return pendingAssistantMessage.bubble.dataset.buffer || "";
  }

  function setArtifactBadge(label = "") {
    const pendingAssistantMessage = state.pendingAssistantMessages.get(state.latestPendingKey);
    if (!pendingAssistantMessage) return;

    const normalizedLabel = String(label || "").trim();
    const { bubble } = pendingAssistantMessage;
    let badgeEl = bubble.querySelector(".chat-msg__artifact-badge");

    if (!normalizedLabel) {
      badgeEl?.remove();
      return;
    }

    if (!badgeEl) {
      badgeEl = document.createElement("div");
      badgeEl.className = "chat-msg__artifact-badge";
      bubble.appendChild(badgeEl);
    }
    badgeEl.textContent = normalizedLabel;
  }

  function finalizeAssistantBubble() {
    state.pendingAssistantMessages.forEach((pendingAssistantMessage) => {
      pendingAssistantMessage.bubble.classList.remove("is-typing");
      if (pendingAssistantMessage.headerStatusEl) {
        pendingAssistantMessage.headerStatusEl.hidden = true;
      }
      if (pendingAssistantMessage.footerStatusEl) {
        pendingAssistantMessage.footerStatusEl.remove();
      }
    });
    state.pendingAssistantMessages.clear();
    state.latestPendingKey = "assistant:default";
  }

  function reset() {
    state.pendingAssistantMessages.clear();
    state.latestPendingKey = "assistant:default";
  }

  return {
    appendMessage,
    appendTimelineStatus,
    applyTokenChunk,
    getPendingBuffer,
    setArtifactBadge,
    finalizeAssistantBubble,
    reset,
  };
}
