import { t } from "../../../i18n.js";

export function createMessageRenderer({ timelineEl, renderMarkdown }) {
  const state = {
    pendingAssistantMessage: null,
  };

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
    timestamp.textContent = new Date().toLocaleTimeString("zh-TW", { hour12: false });
    footer.appendChild(timestamp);

    const footerStatusEl = document.createElement("span");
    footerStatusEl.className = "chat-msg__meta-status";
    if (meta.status) {
      footerStatusEl.textContent = meta.status;
      footer.appendChild(footerStatusEl);
    }

    message.appendChild(footer);

    timelineEl.appendChild(message);
    timelineEl.scrollTop = timelineEl.scrollHeight;
    return { message, bubble, bubbleBody, headerStatusEl, footerStatusEl };
  }

  function appendTimelineStatus(message) {
    const item = document.createElement("div");
    item.className = "timeline-status";
    item.textContent = message;
    timelineEl.appendChild(item);
    timelineEl.scrollTop = timelineEl.scrollHeight;
  }

  function applyTokenChunk(text = "") {
    if (!state.pendingAssistantMessage) {
      state.pendingAssistantMessage = appendMessage("agent", "", { status: t("chat.status.streaming"), typing: true });
      state.pendingAssistantMessage.bubble.dataset.buffer = "";
    }
    state.pendingAssistantMessage.bubble.dataset.buffer = `${state.pendingAssistantMessage.bubble.dataset.buffer || ""}${text}`;
    state.pendingAssistantMessage.bubble.classList.remove("is-typing");
    state.pendingAssistantMessage.bubbleBody.innerHTML = renderMarkdown(state.pendingAssistantMessage.bubble.dataset.buffer);
    timelineEl.scrollTop = timelineEl.scrollHeight;
  }

  function finalizeAssistantBubble() {
    if (state.pendingAssistantMessage) {
      state.pendingAssistantMessage.bubble.classList.remove("is-typing");
      if (state.pendingAssistantMessage.headerStatusEl) {
        state.pendingAssistantMessage.headerStatusEl.hidden = true;
      }
      if (state.pendingAssistantMessage.footerStatusEl) {
        state.pendingAssistantMessage.footerStatusEl.remove();
      }
    }
    state.pendingAssistantMessage = null;
  }

  function reset() {
    state.pendingAssistantMessage = null;
  }

  return {
    appendMessage,
    appendTimelineStatus,
    applyTokenChunk,
    finalizeAssistantBubble,
    reset,
  };
}
