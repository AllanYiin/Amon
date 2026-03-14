import { createMessageRenderer } from "./chat/renderers/messageRenderer.js";
import { createTimelineRenderer } from "./chat/renderers/timelineRenderer.js";
import { createInputBar } from "./chat/renderers/inputBar.js";
import { createStreamingArtifactParser } from "./chat/renderers/streamingArtifactParser.js";
import { buildPreviewForFiles, revoke as revokeInlinePreviewUrl } from "./chat/renderers/inlineArtifactPreview.js";
import { renderInlineArtifactsList, renderInlineArtifactStreamingHint, showInlineArtifactPreview } from "../layout/inlineArtifactsBinder.js";
import { hasConcreteProjectId, normalizeProjectIdForUi } from "../domain/projectId.js";
import { logViewInitDebug } from "../utils/debug.js";

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
  persistWhileStreaming: true,
  mount(ctx) {
    const { elements, appState, store, t, ui } = ctx;
    if (!elements?.timeline || !elements?.chatForm || !EventStreamClient) return;
    const getConcreteProjectId = () => normalizeProjectIdForUi(appState.projectId);
    logViewInitDebug("chat", {
      project_id: getConcreteProjectId() || null,
      run_id: appState.graphRunId || null,
      thread_id: appState.activeThreadId || null,
      node_states_count: Object.keys(appState.graphNodeStates || {}).length,
    });

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
      sendButtonEl: elements.chatSend,
      cancelButtonEl: elements.chatCancel,
      onSubmit: (message, files) => {
        void startStream(message, files);
      },
    });

    let streamAbortController = null;
    let streamCompleted = false;
    let receivedSoftWarning = false;
    const artifactParser = createStreamingArtifactParser();
    const inlineFiles = new Map();
    const inlinePreviewUrls = new Map();
    let activeInlinePreviewUrl = null;

    const setStreamStatus = (text = "") => {
      if (!elements.chatStreamStatus) return;
      elements.chatStreamStatus.textContent = String(text || "").trim();
    };

    const setStreaming = (active) => {
      appState.streaming = active;
      elements.streamProgress.hidden = !active;
      if (elements.chatStreamStatus) {
        elements.chatStreamStatus.hidden = !active;
      }
      if (!active) {
        setStreamStatus("");
      }
      inputBar.setDisabled(active);
    };

    const activateArtifactsTab = ({ collapsed = false } = {}) => {
      const layoutState = store.getState().layout || {};
      const inspectorState = layoutState.inspector || {};
      store.patch({
        layout: {
          ...layoutState,
          inspector: {
            ...inspectorState,
            activeTab: "artifacts",
            collapsed,
          },
        },
      });
    };

    const refreshInlineArtifactsUi = () => {
      renderInlineArtifactsList(elements, appState.inlineArtifacts || [], onSelectInlineArtifact);
      renderInlineArtifactStreamingHint(elements, appState.inlineArtifactStreamingHint || "");
      if ((appState.inlineArtifacts || []).length > 0) {
        elements.artifactsEmpty.hidden = true;
        elements.artifactsListDetails.hidden = false;
      }
    };

    // 聊天頁預設維持右側收合，僅在偵測到具檔名 inline artifact 時展開
    activateArtifactsTab({ collapsed: true });

    const applyInlineArtifactEvents = (artifactEvents = []) => {
      artifactEvents.forEach((artifactEvent) => {
        if (artifactEvent.type === "artifact_open") {
          appState.inlineArtifactStreamingHint = `偵測到 inline artifact 串流中：${artifactEvent.filename}`;
          activateArtifactsTab({ collapsed: false });
          renderInlineArtifactStreamingHint(elements, appState.inlineArtifactStreamingHint);
          return;
        }
        if (artifactEvent.type !== "artifact_complete") {
          return;
        }

        inlineFiles.set(artifactEvent.filename, {
          filename: artifactEvent.filename,
          language: artifactEvent.language,
          content: artifactEvent.content,
        });
        appState.inlineArtifactFiles = Object.fromEntries(inlineFiles.entries());

        for (const [filename, previousUrl] of inlinePreviewUrls.entries()) {
          const preview = buildPreviewForFiles(inlineFiles, { preferredFilename: filename });
          inlinePreviewUrls.set(filename, preview.url);
          if (previousUrl && previousUrl !== preview.url) {
            revokeInlinePreviewUrl(previousUrl);
          }
        }

        for (const file of inlineFiles.values()) {
          if (inlinePreviewUrls.has(file.filename)) continue;
          const preview = buildPreviewForFiles(inlineFiles, { preferredFilename: file.filename });
          inlinePreviewUrls.set(file.filename, preview.url);
        }

        const selectedUrl = inlinePreviewUrls.get(artifactEvent.filename) || "";
        activeInlinePreviewUrl = selectedUrl;
        const nextInlineArtifacts = Array.from(inlineFiles.values()).map((file) => ({
          id: `inline:${file.filename}`,
          filename: file.filename,
          name: file.filename,
          mime: "text/html",
          url: inlinePreviewUrls.get(file.filename) || "",
          createdAt: new Date().toISOString(),
          source: "inline",
        }));

        appState.inlineArtifacts = nextInlineArtifacts;
        appState.artifactPreviewItem = {
          id: `inline:${artifactEvent.filename}`,
          name: artifactEvent.filename,
          mime: "text/html",
          url: selectedUrl,
          source: "inline",
        };
        appState.inlineArtifactStreamingHint = `已完成 inline artifact：${artifactEvent.filename}`;

        activateArtifactsTab({ collapsed: false });
        refreshInlineArtifactsUi();
        showInlineArtifactPreview(elements, {
          name: artifactEvent.filename,
          url: selectedUrl,
        });
      });
    };


    const onSelectInlineArtifact = (artifactItem) => {
      if (!artifactItem?.url) return;
      activeInlinePreviewUrl = artifactItem.url;
      appState.artifactPreviewItem = {
        id: artifactItem.id || `inline:${artifactItem.filename || artifactItem.name || "artifact"}`,
        name: artifactItem.filename || artifactItem.name || "inline artifact",
        mime: artifactItem.mime || "text/html",
        url: artifactItem.url,
        source: "inline",
      };
      showInlineArtifactPreview(elements, {
        name: artifactItem.filename || artifactItem.name,
        url: artifactItem.url,
      });
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
        if (!streamCompleted) {
          ui.toast?.show(`串流暫時中斷（${ctx.chatDeps.formatUnknownValue(transport, "未知傳輸")}），系統正在嘗試續傳。`, {
            type: "warning",
            duration: 7000,
          });
        }
      } else if (status === "error") {
        if (streamCompleted || receivedSoftWarning) {
          return;
        }
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
      appState.inlineArtifactStreamingHint = "";
      renderInlineArtifactStreamingHint(elements, "");
      setStreaming(false);
      messageRenderer.finalizeAssistantBubble();
    };

    const cancelStream = () => {
      if (!appState.streaming && !streamAbortController && !appState.streamClient) {
        return;
      }
      stopStream();
      messageRenderer.appendTimelineStatus("已取消目前執行。");
      ctx.chatDeps.updateThinking({ status: "idle", brief: "已取消目前執行" });
      ui.toast?.show("已取消目前執行。", { type: "info", duration: 4000 });
    };

    const startStream = async (message, attachments = []) => {
      stopStream();
      streamCompleted = false;
      receivedSoftWarning = false;
      streamAbortController = new AbortController();
      artifactParser.reset();
      inlineFiles.clear();
      inlinePreviewUrls.forEach((url) => revokeInlinePreviewUrl(url));
      inlinePreviewUrls.clear();
      appState.inlineArtifacts = [];
      appState.inlineArtifactFiles = {};
      appState.inlineArtifactStreamingHint = "";
      activateArtifactsTab({ collapsed: true });
      renderInlineArtifactStreamingHint(elements, "");
      ctx.chatDeps.resetPlanCard();

      const finalMessage = `${message}${buildAttachmentSummary(attachments)}`;
      messageRenderer.appendMessage("user", finalMessage);
      messageRenderer.appendTimelineStatus("訊息已送出，等待事件回傳中...");
      setStreamStatus("已送出任務，正在等待規劃器回應…");
      ctx.chatDeps.updateThinking({ status: "processing", brief: "需求已送出，等待 reasoning 摘要" });
      timelineRenderer.updateExecutionStep("thinking", { title: "Thinking", status: "running", details: "訊息已送出，等待模型分析" });
      timelineRenderer.updateExecutionStep("planning", { title: "Planning", status: "pending", details: "尚未開始規劃" });
      timelineRenderer.updateExecutionStep("tool_execution", { title: "Tool execution", status: "pending", details: "等待工具呼叫" });
      timelineRenderer.updateExecutionStep("node_status", { title: "Node 狀態", status: "pending", details: "等待 run/node 事件", inferred: true });
      setStreaming(true);

      const messageLength = finalMessage.length;
      let streamToken = null;
      const activeProjectId = getConcreteProjectId() || null;
      if (messageLength > 1800) {
        try {
          const response = await fetch("/v1/threads/stream/init", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: streamAbortController.signal,
            body: JSON.stringify({
              message: finalMessage,
              project_id: activeProjectId,
              thread_id: appState.activeThreadId,
            }),
          });
          if (!response.ok) {
            throw new Error(`stream init failed: ${response.status}`);
          }
          const payload = await response.json();
          streamToken = payload.stream_token || null;
          if (!streamToken) {
            throw new Error("stream token missing");
          }
        } catch (error) {
          if (streamAbortController?.signal.aborted || error?.name === "AbortError") {
            stopStream();
            return;
          }
          ui.toast?.show("訊息較長，初始化串流失敗，請稍後重試。", { type: "danger", duration: 9000 });
          stopStream();
          return;
        }
      }

      appState.streamClient = new EventStreamClient({
        preferSSE: true,
        // Allow short transient SSE hiccups to recover before showing a fatal toast.
        maxReconnectAttempts: 3,
        sseUrlBuilder: (params, lastEventId) => {
          const query = new URLSearchParams();
          if (params.stream_token) {
            query.set("stream_token", params.stream_token);
          } else {
            query.set("message", params.message);
          }
          if (params.project_id) query.set("project_id", params.project_id);
          if (params.thread_id) query.set("thread_id", params.thread_id);
          if (lastEventId) query.set("last_event_id", lastEventId);
          return `/v1/threads/stream?${query.toString()}`;
        },
        wsUrlBuilder: (params, lastEventId) => {
          const protocol = window.location.protocol === "https:" ? "wss" : "ws";
          const query = new URLSearchParams();
          if (params.stream_token) {
            query.set("stream_token", params.stream_token);
          } else {
            query.set("message", params.message);
          }
          if (params.project_id) query.set("project_id", params.project_id);
          if (params.thread_id) query.set("thread_id", params.thread_id);
          if (lastEventId) query.set("last_event_id", lastEventId);
          return `${protocol}://${window.location.host}/v1/threads/stream?${query.toString()}`;
        },
        onStatusChange: ({ status, transport }) => updateDaemonStatus(status, transport),
        onEvent: async (eventType, data) => {
          if (streamAbortController?.signal.aborted) return;
          try {
            appState.uiStore.applyEvent(eventType, data);
            ctx.bus?.emit?.("stream:event", { eventType, data });
            await ctx.chatDeps.applySessionFromEvent(data);
            if (hasConcreteProjectId(appState.projectId) && ["result", "done", "notice"].includes(eventType)) {
              await ctx.chatDeps.loadContext();
            }
            timelineRenderer.applyExecutionEvent(eventType, data);
            if (eventType === "reasoning") {
              const reasoningText = String(data.text || "").trim();
              if (reasoningText) {
                setStreamStatus(reasoningText);
              }
              ctx.chatDeps.updateThinking({ status: "reasoning", brief: "收到 reasoning 摘要", verbose: data.text || "" });
              return;
            }
            if (eventType === "warning") {
              const warningKind = String(data.kind || "").toLowerCase();
              if (warningKind.includes("timeout")) {
                receivedSoftWarning = true;
              }
              ui.toast?.show(data.message || "系統回覆較慢，仍在繼續處理。", { type: "warning", duration: 7000 });
              return;
            }
            if (eventType === "token") {
              messageRenderer.applyTokenChunk(data.text || "");
              applyInlineArtifactEvents(artifactParser.feed(data.text || ""));
              return;
            }
            if (eventType === "notice") {
              if (data.text) {
                setStreamStatus(String(data.text).replace(/^Amon：/, "").trim());
                messageRenderer.appendMessage("agent", data.text);
              }
              return;
            }
            if (eventType === "todo") {
              const markdown = String(data.markdown || "").trim();
              if (markdown) {
                messageRenderer.appendMessage("agent", markdown);
                messageRenderer.appendTimelineStatus("已產出 TODO 初稿，開始概念對齊與詳細規劃。");
                if (hasConcreteProjectId(appState.projectId)) {
                  await ctx.chatDeps.loadContext();
                }
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
              artifactParser.feed("\n");
              applyInlineArtifactEvents(artifactParser.finalizeClosedArtifacts());
              ctx.chatDeps.updateThinking({ status: "error", brief: data.message || "流程失敗" });
              ui.toast?.show(data.message || "串流失敗", { type: "danger", duration: 9000 });
              stopStream();
              return;
            }
            if (eventType === "done") {
              artifactParser.feed("\n");
              applyInlineArtifactEvents(artifactParser.finalizeClosedArtifacts());
              streamCompleted = true;
              await ctx.chatDeps.applySessionFromEvent(data);
              const doneStatus = data.status || "ok";
              if (doneStatus !== "ok" && doneStatus !== "confirm_required" && doneStatus !== "warning" && doneStatus !== "project_required") {
                messageRenderer.appendMessage("agent", `流程結束（${doneStatus}）。我已收到你的訊息，請調整描述後再送出，我會持續回應。`);
                messageRenderer.appendTimelineStatus(`流程狀態：${doneStatus}`);
              }
              if (data.final_text) {
                messageRenderer.appendMessage("agent", data.final_text);
              }
              const phaseMetrics = data.phase_metrics || {};
              const totalMs = Number(phaseMetrics.total_ms || 0);
              if (totalMs > 0) {
                messageRenderer.appendTimelineStatus(`規劃與執行耗時約 ${(totalMs / 1000).toFixed(1)} 秒。`);
                const routeMs = Number(phaseMetrics.route_intent_ms || 0);
                const executionModeMs = Number(phaseMetrics.execution_mode_ms || 0);
                const segments = [
                  ["路由", routeMs],
                  [executionModeMs > 0 && executionModeMs === routeMs ? "模式判斷(併入路由)" : "模式判斷", executionModeMs],
                  ["TODO 初稿", Number(phaseMetrics.todo_bootstrap_ms || 0)],
                  ["詳細規劃", Number(phaseMetrics.plan_generation_ms || 0)],
                  ["編譯圖", Number(phaseMetrics.compile_graph_ms || 0)],
                  ["執行圖", Number(phaseMetrics.run_graph_ms || 0)],
                ]
                  .filter(([, value]) => value > 0)
                  .map(([label, value]) => `${label} ${(value / 1000).toFixed(1)}s`);
                if (segments.length) {
                  messageRenderer.appendTimelineStatus(`耗時拆解：${segments.join("｜")}`);
                }
              }
              ctx.chatDeps.updateThinking({ status: doneStatus === "ok" ? "done" : doneStatus, brief: doneStatus === "ok" ? "流程已完成" : `流程結束：${doneStatus}` });
              stopStream();
              await ctx.chatDeps.loadProjects();
              if (hasConcreteProjectId(appState.projectId)) {
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
        message: streamToken ? "" : finalMessage,
        stream_token: streamToken,
        project_id: activeProjectId,
        thread_id: appState.activeThreadId,
      });
    };

    const unbindInput = inputBar.bind();
    const onCancelStream = () => cancelStream();
    elements.chatCancel?.addEventListener("click", onCancelStream);
    setStreaming(Boolean(appState.streaming && appState.streamClient));
    this.__chatCleanup = () => {
      unbindInput?.();
      elements.chatCancel?.removeEventListener("click", onCancelStream);
      stopStream();
      inlinePreviewUrls.forEach((url) => revokeInlinePreviewUrl(url));
      inlinePreviewUrls.clear();
      activeInlinePreviewUrl = null;
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
