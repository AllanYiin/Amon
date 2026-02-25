import { t } from "../i18n.js";
import { logViewInitDebug } from "../utils/debug.js";

const CONTEXT_COLORS = {
  project_context: "#22c55e",
  system_prompt: "#6366f1",
  tools_definition: "#06b6d4",
  skills: "#10b981",
  tool_use: "#f59e0b",
  chat_history: "#ec4899",
};

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

async function refreshContextStats(ctx, rootEl, projectId) {
  if (!projectId) {
    setDashboardUnavailable(rootEl);
    return null;
  }
  try {
    const statsPayload = await ctx.services.context.getContextStats(projectId);
    renderContextStats(rootEl, statsPayload);
    return statsPayload;
  } catch (error) {
    setDashboardUnavailable(rootEl);
    throw error;
  }
}

function renderWaffle(rootEl, categories = [], usedPercent = 0) {
  const waffle = rootEl.querySelector("#context-waffle-grid");
  if (!waffle) return;
  waffle.innerHTML = "";

  const totalCells = 100;
  const usedCells = Math.max(0, Math.min(totalCells, Math.round(usedPercent)));
  const totalTokens = categories.reduce((sum, item) => sum + Number(item.tokens || 0), 0);

  const assignments = [];
  if (usedCells > 0 && totalTokens > 0) {
    categories.forEach((item, index) => {
      const ratio = Number(item.tokens || 0) / totalTokens;
      const isLast = index === categories.length - 1;
      const size = isLast
        ? Math.max(usedCells - assignments.length, 0)
        : Math.max(0, Math.round(usedCells * ratio));
      for (let i = 0; i < size && assignments.length < usedCells; i += 1) {
        assignments.push(item.key);
      }
    });
  }

  while (assignments.length < usedCells) assignments.push("chat_history");

  for (let i = 0; i < totalCells; i += 1) {
    const cell = document.createElement("span");
    cell.className = "context-waffle__cell";
    if (i < usedCells) {
      const key = assignments[i] || "chat_history";
      cell.classList.add("is-used");
      cell.style.backgroundColor = CONTEXT_COLORS[key] || "#7c7cff";
    }
    waffle.appendChild(cell);
  }
}

function renderBreakdown(rootEl, categories = []) {
  const list = rootEl.querySelector("#context-breakdown-list");
  if (!list) return;
  list.innerHTML = "";

  const total = categories.reduce((sum, item) => sum + Number(item.tokens || 0), 0);
  categories.forEach((item) => {
    const tokens = Number(item.tokens || 0);
    const ratio = total > 0 ? (tokens / total) * 100 : 0;
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="context-breakdown__label"><span>${item.label || item.key}</span><span>${tokens.toLocaleString("zh-TW")} tok</span></div>
      <div class="context-breakdown__progress${ratio ? "" : " is-unavailable"}"><span style="width:${Math.max(ratio, 3).toFixed(1)}%; background:${CONTEXT_COLORS[item.key] || "#7c7cff"}"></span></div>
      <small>${item.note || "來源統計"}${item.items ? `｜項目數：${item.items}` : ""}</small>
    `;
    list.appendChild(li);
  });
}

function setDashboardUnavailable(rootEl) {
  const usagePercent = rootEl.querySelector("#context-usage-percent");
  const usageMeta = rootEl.querySelector("#context-usage-meta");
  const status = rootEl.querySelector("#context-usage-status");
  if (usagePercent) usagePercent.textContent = "--";
  if (usageMeta) usageMeta.textContent = "Token 使用量尚未可取得。";
  if (status) status.textContent = "尚未可取得";
  renderWaffle(rootEl, [], 0);
}

function renderContextStats(rootEl, payload) {
  const usagePercent = rootEl.querySelector("#context-usage-percent");
  const usageMeta = rootEl.querySelector("#context-usage-meta");
  const status = rootEl.querySelector("#context-usage-status");
  const remainingEl = rootEl.querySelector("#context-kpi-remaining");
  const costEl = rootEl.querySelector("#context-kpi-cost");

  const estimate = payload?.token_estimate || {};
  const used = Number(estimate.used || 0);
  const capacity = Number(estimate.capacity || 0);
  const ratio = capacity > 0 ? used / capacity : Number(estimate.usage_ratio || 0);
  const percent = Math.max(0, Math.min(100, Math.round(ratio * 100)));

  if (usagePercent) usagePercent.textContent = `${percent}%`;
  if (status) status.textContent = percent >= 80 ? "接近上限" : "可使用";
  if (usageMeta) {
    usageMeta.textContent = `估算 ${used.toLocaleString("zh-TW")} / ${capacity.toLocaleString("zh-TW")} tokens（資料來源：system prompt / tools / skills / tool use / chat history）。`;
  }
  if (remainingEl) remainingEl.textContent = Number(estimate.remaining || 0).toLocaleString("zh-TW");
  if (costEl) costEl.textContent = `US$ ${Number(estimate.estimated_cost_usd || 0).toFixed(4)}`;

  const categories = Array.isArray(payload?.categories) ? payload.categories : [];
  renderWaffle(rootEl, categories, percent);
  renderBreakdown(rootEl, categories);
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
    const statsPayload = await refreshContextStats(ctx, rootEl, projectId);
    dispatchContext(ctx, { context: text, lastSavedAt: Date.now(), stats: statsPayload });
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
    if (scope === "project") {
      setDashboardUnavailable(rootEl);
    } else {
      const statsPayload = await refreshContextStats(ctx, rootEl, getProjectId(ctx));
      dispatchContext(ctx, { stats: statsPayload });
    }
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
    logViewInitDebug("context", {
      project_id: ctx.appState?.projectId || getProjectId(ctx) || null,
      run_id: ctx.appState?.graphRunId || null,
      chat_id: ctx.appState?.chatId || null,
      node_states_count: Object.keys(ctx.appState?.graphNodeStates || {}).length,
    });
    const editor = rootEl.querySelector("#context-draft-input");
    const importInput = rootEl.querySelector("#context-import-file");
    const emptyCta = ensureEmptyCta(rootEl);
    const handlers = [];

    setDashboardUnavailable(rootEl);

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
      setDashboardUnavailable(ctx.rootEl);
      return;
    }
    try {
      const [payload, statsPayload] = await Promise.all([
        ctx.services.context.getContext(projectId),
        refreshContextStats(ctx, ctx.rootEl, projectId),
      ]);
      const contextText = payload?.context || payload?.memory || "";
      if (editor) editor.value = contextText;
      updateDraftMeta(ctx.rootEl, contextText ? "已載入目前專案草稿。" : "目前專案尚無草稿。");
      emptyCta.hidden = Boolean(contextText);
      dispatchContext(ctx, { context: contextText, projectId, loadedAt: Date.now(), stats: statsPayload });
    } catch (error) {
      ctx.ui.toast?.show(t("toast.context.loadFailed", "", { message: error.message }), { type: "danger", duration: 12000 });
      setDashboardUnavailable(ctx.rootEl);
    }
  },
};
