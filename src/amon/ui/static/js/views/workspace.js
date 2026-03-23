function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || ctx.appState?.projectId || "";
}

function renderJson(target, value) {
  if (!target) return;
  target.textContent = JSON.stringify(value, null, 2);
}

function renderOptions(selectEl, items, placeholder) {
  if (!selectEl) return;
  selectEl.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = placeholder;
  selectEl.appendChild(empty);
  (items || []).forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id || "";
    option.textContent = item.name || item.title || item.id || "";
    selectEl.appendChild(option);
  });
}

/** @type {import('./contracts.js').ViewContract} */
export const WORKSPACE_VIEW = {
  id: "workspace",
  route: "/workspace",
  mount(ctx) {
    const { elements, services, ui } = ctx;
    if (!elements?.workspacePage) return;
    let stopStream = null;
    let selectedPreviewId = "";

    function closeStream() {
      if (typeof stopStream === "function") {
        stopStream();
      }
      stopStream = null;
    }

    function renderStreamLine(text) {
      const line = document.createElement("div");
      line.className = "workspace-stream__line";
      line.textContent = text;
      elements.workspaceStream.appendChild(line);
      elements.workspaceStream.scrollTop = elements.workspaceStream.scrollHeight;
    }

    function renderPreview(payload) {
      const preview = payload?.preview || {};
      elements.workspacePreviewTitle.textContent = payload?.id || payload?.name || "尚未選擇預覽";
      elements.workspacePreviewMeta.textContent = `${payload?.media_type || "unknown"} | ${payload?.status || "unknown"}`;
      elements.workspacePreviewBody.textContent =
        preview.preview_kind === "inline_text" ? String(preview.text || "") : JSON.stringify(preview, null, 2);
    }

    async function refreshWorkspace() {
      const projectId = getProjectId(ctx);
      if (!projectId) {
        elements.workspaceStatus.textContent = "尚未選擇專案";
        return;
      }
      const summary = await services.workspace.getProjectSummary(projectId);
      elements.workspaceStatus.textContent = `專案：${summary.project?.name || projectId}`;
      renderJson(elements.workspaceDefinitionsSummary, summary.definition_counts || {});
      renderJson(elements.workspaceRunMeta, {
        recent_run: summary.recent_run,
        resumable_runs: summary.resumable_runs,
        pending_confirmations: summary.pending_confirmations?.length || 0,
      });

      const [workflows, templates, uploads, confirmations] = await Promise.all([
        services.workspace.listDefinitions(projectId, "workflows"),
        services.workspace.listDefinitions(projectId, "templates"),
        services.workspace.listUploads(projectId),
        services.workspace.listConfirmations(projectId),
      ]);
      renderOptions(elements.workspaceWorkflowSelect, workflows, "選擇 workflow");
      renderOptions(elements.workspaceTemplateSelect, templates, "選擇 template");
      renderJson(elements.workspaceDefinitionsList, { workflows, templates });
      renderUploads(uploads);
      renderConfirmations(confirmations);

      const recentRunId = summary.recent_run?.id || "";
      elements.workspaceRunId.value = recentRunId;
      if (recentRunId) {
        startStream(recentRunId);
      }
      if (!selectedPreviewId && uploads[0]?.id) {
        selectedPreviewId = uploads[0].id;
        const previewPayload = await services.workspace.getUploadPreview(projectId, selectedPreviewId);
        renderPreview(previewPayload);
      }
    }

    function renderUploads(uploads) {
      elements.workspaceUploadsList.innerHTML = "";
      (uploads || []).forEach((upload) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "workspace-list__item";
        button.textContent = `${upload.id} | ${upload.media_type || "unknown"} | ${upload.status || "unknown"}`;
        button.addEventListener("click", async () => {
          selectedPreviewId = upload.id;
          const previewPayload = await services.workspace.getUploadPreview(getProjectId(ctx), upload.id);
          renderPreview(previewPayload);
        });
        elements.workspaceUploadsList.appendChild(button);
      });
    }

    function renderConfirmations(confirmations) {
      elements.workspaceConfirmationsList.innerHTML = "";
      (confirmations || []).forEach((item) => {
        const row = document.createElement("div");
        row.className = "workspace-confirmation";
        row.innerHTML = `<div><strong>${item.tool_name || item.id || "confirmation"}</strong><p>${item.reason || ""}</p></div>`;
        const actions = document.createElement("div");
        actions.className = "workspace-confirmation__actions";
        const approve = document.createElement("button");
        approve.type = "button";
        approve.className = "btn btn--primary primary-btn small";
        approve.textContent = "批准";
        approve.addEventListener("click", async () => {
          await services.workspace.approveConfirmation(getProjectId(ctx), item.id);
          ui.toast?.show("已批准 confirmation", { type: "success" });
          await refreshWorkspace();
        });
        const reject = document.createElement("button");
        reject.type = "button";
        reject.className = "btn btn--secondary secondary-btn small";
        reject.textContent = "拒絕";
        reject.addEventListener("click", async () => {
          await services.workspace.rejectConfirmation(getProjectId(ctx), item.id);
          ui.toast?.show("已拒絕 confirmation", { type: "warning" });
          await refreshWorkspace();
        });
        actions.append(approve, reject);
        row.appendChild(actions);
        elements.workspaceConfirmationsList.appendChild(row);
      });
    }

    function startStream(runId) {
      closeStream();
      elements.workspaceStream.innerHTML = "";
      if (!runId) return;
      stopStream = services.workspace.streamRun(getProjectId(ctx), runId, {
        onEvent(type, payload) {
          if (type === "node.chunk") {
            renderStreamLine(payload.text || "");
            return;
          }
          renderStreamLine(JSON.stringify(payload));
        },
        onDone(payload) {
          renderStreamLine(`done: ${payload.status || "completed"}`);
        },
        onError() {
          renderStreamLine("stream interrupted");
        },
      });
    }

    async function handleCreateRun() {
      const projectId = getProjectId(ctx);
      const workflowRef = elements.workspaceWorkflowSelect.value;
      const templateRef = elements.workspaceTemplateSelect.value;
      const execute = elements.workspaceRunExecute.checked;
      const payload = await services.workspace.createRun(projectId, {
        workflow_ref: workflowRef || undefined,
        template_ref: templateRef || undefined,
        execute,
      });
      elements.workspaceRunId.value = payload.run?.id || "";
      renderJson(elements.workspaceRunMeta, payload.run || {});
      if (payload.run?.id) {
        startStream(payload.run.id);
      }
      ui.toast?.show(execute ? "已建立並排入執行" : "已建立 compiled run", { type: "success" });
      await refreshWorkspace();
    }

    async function handleResumeRun() {
      const projectId = getProjectId(ctx);
      const runId = String(elements.workspaceRunId.value || "").trim();
      if (!runId) {
        ui.toast?.show("請先輸入 run ID", { type: "warning" });
        return;
      }
      const payload = await services.workspace.resumeRun(projectId, runId, { execute: true });
      renderJson(elements.workspaceRunMeta, payload.run || {});
      startStream(runId);
      ui.toast?.show("已送出 resume", { type: "success" });
    }

    async function handleUpload() {
      const projectId = getProjectId(ctx);
      const sourcePath = String(elements.workspaceUploadPath.value || "").trim();
      if (!sourcePath) {
        ui.toast?.show("請提供本機檔案路徑", { type: "warning" });
        return;
      }
      const payload = await services.workspace.createUpload(projectId, sourcePath, elements.workspaceUploadNotes.value || "");
      selectedPreviewId = payload.upload?.id || payload.id || "";
      ui.toast?.show("已建立 upload", { type: "success" });
      await refreshWorkspace();
      if (selectedPreviewId) {
        const previewPayload = await services.workspace.getUploadPreview(projectId, selectedPreviewId);
        renderPreview(previewPayload);
      }
    }

    elements.workspaceRefresh?.addEventListener("click", () => void refreshWorkspace());
    elements.workspaceRunStart?.addEventListener("click", () => void handleCreateRun());
    elements.workspaceRunResume?.addEventListener("click", () => void handleResumeRun());
    elements.workspaceUploadAdd?.addEventListener("click", () => void handleUpload());

    this.unmount = () => {
      closeStream();
    };
  },
  async onRoute(_route, ctx) {
    const { elements, services } = ctx;
    if (!elements?.workspacePage) return;
    const projectId = getProjectId(ctx);
    if (!projectId) {
      elements.workspaceStatus.textContent = "請先從左側選擇專案";
      return;
    }
    const summary = await services.workspace.getProjectSummary(projectId);
    elements.workspaceStatus.textContent = `專案：${summary.project?.name || projectId}`;
    elements.workspaceRefresh?.click();
  },
};
