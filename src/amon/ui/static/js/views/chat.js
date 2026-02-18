import { createMessageRenderer } from "./chat/renderers/messageRenderer.js";
import { createTimelineRenderer } from "./chat/renderers/timelineRenderer.js";
import { createInputBar } from "./chat/renderers/inputBar.js";

const { EventStreamClient } = window.AmonUIEventStream || {};

function buildAttachmentSummary(attachments) {
  if (!attachments || attachments.length === 0) return "";
  const lines = attachments.map((file) => {
    const sizeKb = Math.round(file.size / 1024);
    return `- ${file.name} (${file.type || "未知格式"}, ${sizeKb} KB)`;
  });
  return `\n\n[附件摘要]\n${lines.join("\n")}`;
}

/** @type {import('./contracts.js').ViewContract} */
export const CHAT_VIEW = {
  id: "chat",
  route: "/chat",
  mount(ctx) {
    const { elements, appState, store, t, ui } = ctx;
    if (!elements?.timeline || !elements?.chatForm || !EventStreamClient) return;

    const messageRenderer = createMessageRenderer({
      timelineEl: elements.timeline,
      renderMarkdown: ctx.chatDeps.renderMarkdown,
    });
    const timelineRenderer = createTimelineRenderer({
      executionAccordion: elements.executionAccordion,
      executionTimeline: appState.executionTimeline,
      escapeHtml: ctx.chatDeps.escapeHtml,
      shortenId: ctx.chatDeps.shortenId,
      getRunId: () => appState.graphRunId,
    });
    const inputBar = createInputBar({
      formEl: elements.chatForm,
      inputEl: elements.chatInput,
      attachmentsEl: elements.chatAttachments,
      previewEl: elements.attachmentPreview,
      onSubmit: (message, files) => {
        void startStream(message, files);
      },
    });

    let streamAbortController = null;

    const setStreaming = (active) => {
      appState.streaming = active;
      elements.streamProgress.hidden = !active;
      inputBar.setDisabled(false);
    };

    const updateDaemonStatus = (status, transport) => {
      const layoutState = store.getState().layout || {};
      if (status === "connected") {
        store.patch({
          layout: {
            ...layoutState,
            daemonPill: {
              text: `Daemon：${t("status.daemon.healthy")}`,
              level: ctx.chatDeps.mapDaemonStatusLevel("connected"),
              title: "daemon 已連線",
            },
          },
        });
      } else if (status === "reconnecting") {
        store.patch({
          layout: {
            ...layoutState,
            daemonPill: {
              text: `Daemon：${t("status.daemon.reconnecting")}`,
              level: ctx.chatDeps.mapDaemonStatusLevel("reconnecting"),
              title: "daemon 連線中斷，正在重試",
            },
          },
        });
        ui.toast?.show(`串流中斷（${ctx.chatDeps.formatUnknownValue(transport, "未知傳輸")}），請重新送出訊息以續接。`, {
          type: "warning",
          duration: 9000,
        });
        stopStream();
      } else if (status === "error") {
        store.patch({
          layout: {
            ...layoutState,
            daemonPill: {
              text: `Daemon：${t("status.daemon.unavailable")}`,
              level: ctx.chatDeps.mapDaemonStatusLevel("error"),
              title: "daemon 未連線或不可用",
            },
          },
        });
        ui.toast?.show("串流連線失敗，輸入框已恢復可編輯，請重新送出。", { type: "danger", duration: 9000 });
        stopStream();
      }
    };

    const stopStream = () => {
      streamAbortController?.abort();
      streamAbortController = null;
      appState.streamClient?.stop?.();
      appState.streamClient = null;
      setStreaming(false);
      messageRenderer.finalizeAssistantBubble();
    };

    const startStream = async (message, attachments = []) => {
      stopStream();
      streamAbortController = new AbortController();
      ctx.chatDeps.resetPlanCard();

      const finalMessage = `${message}${buildAttachmentSummary(attachments)}`;
      messageRenderer.appendMessage("user", finalMessage);
      messageRenderer.appendTimelineStatus("訊息已送出，等待事件回傳中...");
      ctx.chatDeps.updateThinking({ status: "processing", brief: "需求已送出，等待 reasoning 摘要" });
      timelineRenderer.updateExecutionStep("thinking", { title: "Thinking", status: "running", details: "訊息已送出，等待模型分析" });
      timelineRenderer.updateExecutionStep("planning", { title: "Planning", status: "pending", details: "尚未開始規劃" });
      timelineRenderer.updateExecutionStep("tool_execution", { title: "Tool execution", status: "pending", details: "等待工具呼叫" });
      timelineRenderer.updateExecutionStep("node_status", { title: "Node 狀態", status: "pending", details: "等待 run/node 事件", inferred: true });
      setStreaming(true);

      appState.streamClient = new EventStreamClient({
        preferSSE: true,
        maxReconnectAttempts: 0,
        sseUrlBuilder: (params, lastEventId) => {
          const query = new URLSearchParams({ message: params.message });
          if (params.project_id) query.set("project_id", params.project_id);
          if (params.chat_id) query.set("chat_id", params.chat_id);
          if (lastEventId) query.set("last_event_id", lastEventId);
          return `/v1/chat/stream?${query.toString()}`;
        },
        wsUrlBuilder: (params, lastEventId) => {
          const protocol = window.location.protocol === "https:" ? "wss" : "ws";
          const query = new URLSearchParams({ message: params.message });
          if (params.project_id) query.set("project_id", params.project_id);
          if (params.chat_id) query.set("chat_id", params.chat_id);
          if (lastEventId) query.set("last_event_id", lastEventId);
          return `${protocol}://${window.location.host}/v1/chat/ws?${query.toString()}`;
        },
        onStatusChange: ({ status, transport }) => updateDaemonStatus(status, transport),
        onEvent: async (eventType, data) => {
          if (streamAbortController?.signal.aborted) return;
          try {
            appState.uiStore.applyEvent(eventType, data);
            await ctx.chatDeps.applySessionFromEvent(data);
            if (appState.projectId && ["result", "done", "notice"].includes(eventType)) {
              await ctx.chatDeps.loadContext();
            }
            timelineRenderer.applyExecutionEvent(eventType, data);
            if (eventType === "reasoning") {
              ctx.chatDeps.updateThinking({ status: "reasoning", brief: "收到 reasoning 摘要", verbose: data.text || "" });
              return;
            }
            if (eventType === "token") {
              messageRenderer.applyTokenChunk(data.text || "");
              return;
            }
            if (eventType === "notice") {
              if (data.text) {
                messageRenderer.appendMessage("agent", data.text);
              }
              return;
            }
            if (eventType === "plan") {
              ctx.chatDeps.showPlanCard(data);
              messageRenderer.appendMessage("agent", "已產生 Plan Card，請確認。");
              return;
            }
            if (eventType === "result") {
              ctx.chatDeps.updateThinking({ status: "tool_result", brief: "已收到工具結果" });
              messageRenderer.appendMessage("agent", `\n\n\`\`\`json\n${JSON.stringify(data, null, 2)}\n\`\`\``);
              return;
            }
            if (eventType === "error") {
              ctx.chatDeps.updateThinking({ status: "error", brief: data.message || "流程失敗" });
              ui.toast?.show(data.message || "串流失敗", { type: "danger", duration: 9000 });
              return;
            }
            if (eventType === "done") {
              await ctx.chatDeps.applySessionFromEvent(data);
              const doneStatus = data.status || "ok";
              if (doneStatus !== "ok" && doneStatus !== "confirm_required") {
                messageRenderer.appendMessage("agent", `流程結束（${doneStatus}）。我已收到你的訊息，請調整描述後再送出，我會持續回應。`);
                messageRenderer.appendTimelineStatus(`流程狀態：${doneStatus}`);
              }
              if (data.final_text) {
                messageRenderer.appendMessage("agent", data.final_text);
              }
              ctx.chatDeps.updateThinking({ status: doneStatus === "ok" ? "done" : doneStatus, brief: doneStatus === "ok" ? "流程已完成" : `流程結束：${doneStatus}` });
              stopStream();
              await ctx.chatDeps.loadProjects();
              if (appState.projectId) {
                await ctx.chatDeps.loadContext();
                ctx.chatDeps.appendArtifactsHintToTimeline(appState.runArtifacts.length);
              }
            }
          } catch (error) {
            console.error("stream_event_error", error);
            ui.toast?.show(`事件處理失敗：${error.message || error}`, { type: "danger", duration: 9000 });
          }
        },
      });

      appState.streamClient.start({
        message: finalMessage,
        project_id: appState.projectId,
        chat_id: appState.chatId,
      });
    };

    const unbindInput = inputBar.bind();
    this.__chatCleanup = () => {
      unbindInput?.();
      stopStream();
    };
    this.__chatStartStream = startStream;
    this.__chatStopStream = stopStream;
    this.__chatAppendMessage = messageRenderer.appendMessage;
    this.__chatRenderAttachments = inputBar.renderAttachmentPreview;
  },
  unmount() {
    this.__chatCleanup?.();
    this.__chatCleanup = null;
    this.__chatStartStream = null;
    this.__chatStopStream = null;
    this.__chatAppendMessage = null;
    this.__chatRenderAttachments = null;
  },
  onRoute: async () => {},
};
