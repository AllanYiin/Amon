import { t } from "../i18n.js";

function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || "";
}

function dispatchContext(ctx, payload = {}) {
  ctx.store?.dispatch?.({ type: "@@store/patch", payload: { contextView: payload } });
}

function ensureEmptyCta(rootEl) {
  let box = rootEl.querySelector("[data-context-empty]");
  if (!box) {
    box = document.createElement("div");
    box.className = "empty-context";
    box.dataset.contextEmpty = "true";
    box.innerHTML = `<p>${t("view.context.empty")}</p><button type="button" class="primary-btn" data-context-create>${t("view.context.create")}</button>`;
    rootEl.prepend(box);
  }
  return box;
}

function updateDraftMeta(rootEl, text) {
  const meta = rootEl.querySelector("#context-draft-meta");
  if (!meta) return;
  meta.textContent = text;
}

function ensureGaugeChart(rootEl, local) {
  const canvas = rootEl.querySelector("#context-usage-chart");
  if (!(canvas instanceof HTMLCanvasElement) || typeof window.Chart === "undefined") return;
  if (local.chart) return;
  local.chart = new window.Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: ["used", "available"],
      datasets: [{
        data: [0, 1],
        backgroundColor: ["#7c7cff", "rgba(148, 163, 184, 0.2)"],
        borderWidth: 0,
      }],
    },
    options: {
      animation: false,
      cutout: "72%",
      plugins: {
        tooltip: { enabled: false },
        legend: { display: false },
      },
    },
  });
}

function setDashboardUnavailable(rootEl, local) {
  ensureGaugeChart(rootEl, local);
  const usagePercent = rootEl.querySelector("#context-usage-percent");
  const usageMeta = rootEl.querySelector("#context-usage-meta");
  const status = rootEl.querySelector("#context-usage-status");
  if (usagePercent) usagePercent.textContent = "--";
  if (usageMeta) usageMeta.textContent = "Token 使用量尚未可取得。";
  if (status) status.textContent = "尚未可取得";
  if (local.chart) {
    local.chart.data.datasets[0].data = [0, 1];
    local.chart.update();
  }
}

async function saveDraft(ctx, rootEl, editor) {
  const projectId = getProjectId(ctx);
  if (!projectId) {
    ctx.ui.toast?.show(t("toast.context.selectProject"), { type: "warning", duration: 9000 });
    return;
  }
  try {
    const text = editor?.value || "";
    await ctx.services.context.saveContext(projectId, text);
    dispatchContext(ctx, { context: text, lastSavedAt: Date.now() });
    updateDraftMeta(rootEl, `已儲存本機草稿（${new Date().toLocaleString("zh-TW")})。`);
    ctx.ui.toast?.show(t("toast.context.saved"), { type: "success", duration: 9000 });
  } catch (error) {
    ctx.ui.toast?.show(t("toast.context.saveFailed", "", { message: error.message }), { type: "danger", duration: 12000 });
  }
}

async function clearDraft(ctx, rootEl, editor, scope) {
  const confirmed = await ctx.ui.modal?.open({
    title: t("modal.context.clearTitle"),
    description: t(scope === "project" ? "modal.context.clearDescription.project" : "modal.context.clearDescription.chat"),
    confirmText: t("modal.context.clearConfirm"),
    cancelText: t("modal.context.clearCancel"),
  });
  if (!confirmed) return;
  try {
    await ctx.services.context.clearContext(scope, getProjectId(ctx));
    if (editor) editor.value = "";
    dispatchContext(ctx, { context: "", clearedScope: scope, clearedAt: Date.now() });
    updateDraftMeta(rootEl, scope === "project" ? "已清空專案 Context 草稿。" : "已清空本次對話 Context 草稿。");
    ctx.ui.toast?.show(t("toast.context.cleared"), { type: "success", duration: 9000 });
  } catch (error) {
    ctx.ui.toast?.show(t("toast.context.clearFailed", "", { message: error.message }), { type: "danger", duration: 12000 });
  }
}

function importContextDraftFromFile(rootEl, editor, file, toast) {
  if (!file || !(editor instanceof HTMLTextAreaElement)) return;
  const reader = new FileReader();
  reader.onload = () => {
    editor.value = String(reader.result || "");
    updateDraftMeta(rootEl, `已匯入檔案：${file.name}`);
    toast?.show(`已匯入 ${file.name}，請確認內容後儲存。`, { type: "success", duration: 9000 });
  };
  reader.onerror = () => {
    toast?.show("檔案匯入失敗，請確認編碼與格式。", { type: "danger", duration: 12000 });
  };
  reader.readAsText(file);
}

function extractContextFromChat(rootEl, editor, toast) {
  if (!(editor instanceof HTMLTextAreaElement)) return;
  const latestUser = [...document.querySelectorAll(".chat-bubble.user")].pop();
  if (!latestUser) {
    toast?.show("目前沒有可擷取的使用者對話內容。", { type: "warning", duration: 9000 });
    return;
  }
  const text = (latestUser.textContent || "").replace(/^你：/, "").trim();
  editor.value = text;
  updateDraftMeta(rootEl, "已帶入最近一則使用者對話，請確認後儲存。");
  toast?.show("已從最近對話擷取 Context 草稿。", { type: "success", duration: 9000 });
}

/** @type {import('./contracts.js').ViewContract} */
export const CONTEXT_VIEW = {
  id: "context",
  route: "/context",
  mount: (ctx) => {
    const { rootEl } = ctx;
    if (!rootEl) return;
    const editor = rootEl.querySelector("#context-draft-input");
    const importInput = rootEl.querySelector("#context-import-file");
    const emptyCta = ensureEmptyCta(rootEl);
    const local = { chart: null };
    const handlers = [];

    setDashboardUnavailable(rootEl, local);

    const onClick = async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      if (target.closest("[data-context-create]")) {
        editor?.focus();
        return;
      }

      if (target.id === "context-save-draft" || target.id === "context-save-draft-cta") {
        await saveDraft(ctx, rootEl, editor);
        return;
      }

      if (target.id === "context-clear-chat" || target.id === "context-clear-project") {
        const scope = target.id === "context-clear-project" ? "project" : "chat";
        await clearDraft(ctx, rootEl, editor, scope);
        return;
      }

      if (target.id === "context-extract-chat") {
        extractContextFromChat(rootEl, editor, ctx.ui.toast);
      }
    };

    const onImportChange = (event) => {
      const file = event.target?.files?.[0];
      importContextDraftFromFile(rootEl, editor, file, ctx.ui.toast);
      if (importInput) importInput.value = "";
    };

    rootEl.addEventListener("click", onClick);
    importInput?.addEventListener("change", onImportChange);
    handlers.push(() => rootEl.removeEventListener("click", onClick));
    handlers.push(() => importInput?.removeEventListener("change", onImportChange));

    ctx.__cleanup = () => {
      if (local.chart) {
        local.chart.destroy();
        local.chart = null;
      }
      handlers.forEach((fn) => fn());
    };

    emptyCta.hidden = Boolean(editor?.value);
  },
  unmount() {
    this.__cleanup?.();
    this.__cleanup = null;
  },
  onRoute: async (_params = {}, ctx) => {
    const editor = ctx.rootEl?.querySelector("#context-draft-input");
    const emptyCta = ensureEmptyCta(ctx.rootEl);
    const projectId = getProjectId(ctx);
    if (!projectId) {
      if (editor) editor.value = "";
      updateDraftMeta(ctx.rootEl, "尚未儲存草稿。請先選擇專案。");
      emptyCta.hidden = false;
      dispatchContext(ctx, { context: "", projectId: "" });
      return;
    }
    try {
      const payload = await ctx.services.context.getContext(projectId);
      const contextText = payload?.context || payload?.memory || "";
      if (editor) editor.value = contextText;
      updateDraftMeta(ctx.rootEl, contextText ? "已載入目前專案草稿。" : "目前專案尚無草稿。");
      emptyCta.hidden = Boolean(contextText);
      dispatchContext(ctx, { context: contextText, projectId, loadedAt: Date.now() });
    } catch (error) {
      ctx.ui.toast?.show(t("toast.context.loadFailed", "", { message: error.message }), { type: "danger", duration: 12000 });
    }
  },
};
