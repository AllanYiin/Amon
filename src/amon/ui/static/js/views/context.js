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
    box.innerHTML = '<p>尚未載入 Context，請先輸入專案背景。</p><button type="button" class="primary-btn" data-context-create>新增 Context</button>';
    rootEl.prepend(box);
  }
  return box;
}

/** @type {import('./contracts.js').ViewContract} */
export const CONTEXT_VIEW = {
  id: "context",
  route: "/context",
  mount: (ctx) => {
    const { rootEl } = ctx;
    if (!rootEl) return;
    const editor = rootEl.querySelector("#context-draft-input");
    const emptyCta = ensureEmptyCta(rootEl);
    const handlers = [];

    const onClick = async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;

      if (target.closest("[data-context-create]")) {
        editor?.focus();
        return;
      }

      if (target.id === "context-save-draft") {
        const projectId = getProjectId(ctx);
        if (!projectId) {
          ctx.ui.toast?.show("請先選擇專案後再儲存 Context。", { type: "warning", duration: 9000 });
          return;
        }
        try {
          await ctx.services.context.saveContext(projectId, editor?.value || "");
          dispatchContext(ctx, { context: editor?.value || "", lastSavedAt: Date.now() });
          ctx.ui.toast?.show("Context 已儲存。", { type: "success", duration: 9000 });
        } catch (error) {
          ctx.ui.toast?.show(`儲存失敗：${error.message}`, { type: "danger", duration: 12000 });
        }
      }

      if (target.id === "context-clear-chat" || target.id === "context-clear-project") {
        const scope = target.id === "context-clear-project" ? "project" : "chat";
        const confirmed = await ctx.ui.modal?.open({
          title: "確認清空 Context",
          description: `確定要清空 ${scope === "project" ? "專案" : "本次對話"} Context 嗎？`,
          confirmText: "清空",
          cancelText: "取消",
        });
        if (!confirmed) return;
        try {
          await ctx.services.context.clearContext(scope, getProjectId(ctx));
          if (editor) editor.value = "";
          dispatchContext(ctx, { context: "", clearedScope: scope, clearedAt: Date.now() });
          ctx.ui.toast?.show("Context 已清空。", { type: "success", duration: 9000 });
        } catch (error) {
          ctx.ui.toast?.show(`清空失敗：${error.message}`, { type: "danger", duration: 12000 });
        }
      }
    };

    rootEl.addEventListener("click", onClick);
    handlers.push(() => rootEl.removeEventListener("click", onClick));
    ctx.__cleanup = () => handlers.forEach((fn) => fn());

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
      emptyCta.hidden = false;
      dispatchContext(ctx, { context: "", projectId: "" });
      return;
    }
    try {
      const payload = await ctx.services.context.getContext(projectId);
      const contextText = payload?.context || payload?.memory || "";
      if (editor) editor.value = contextText;
      emptyCta.hidden = Boolean(contextText);
      dispatchContext(ctx, { context: contextText, projectId, loadedAt: Date.now() });
    } catch (error) {
      ctx.ui.toast?.show(`載入 Context 失敗：${error.message}`, { type: "danger", duration: 12000 });
    }
  },
};
