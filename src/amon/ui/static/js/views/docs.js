import { t } from "../i18n.js";

function getProjectId(ctx) {
  return ctx.store?.getState?.()?.layout?.projectId || "";
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderDocContent(content, docPath) {
  const isMarkdown = /\.(md|markdown)$/i.test(docPath || "");
  if (isMarkdown && window.marked) {
    const html = window.marked.parse(content || "");
    return window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
  }
  return `<pre><code>${escapeHtml(content || "")}</code></pre>`;
}

/** @type {import('./contracts.js').ViewContract} */
export const DOCS_VIEW = {
  id: "docs",
  route: "/docs",
  mount: (ctx) => {
    const { rootEl } = ctx;
    if (!rootEl) return;
    const state = { docs: [], filtered: [], selected: "" };

    const viewport = rootEl.querySelector("#docs-tree-viewport");
    const filterInput = rootEl.querySelector("#docs-filter");
    const refreshBtn = rootEl.querySelector("#docs-refresh");
    const metaEl = rootEl.querySelector("#docs-tree-meta");
    const titleEl = rootEl.querySelector("#docs-preview-title");
    const previewEl = rootEl.querySelector("#docs-preview-content");

    function dispatch(payload) {
      ctx.store?.dispatch?.({ type: "@@store/patch", payload: { docsView: payload } });
    }

    function applyFilter() {
      const q = (filterInput?.value || "").trim().toLowerCase();
      state.filtered = q
        ? state.docs.filter((doc) => `${doc.name} ${doc.path}`.toLowerCase().includes(q))
        : [...state.docs];
      metaEl.textContent = t("view.docs.meta", "", { filtered: state.filtered.length, total: state.docs.length });
      viewport.innerHTML = "";
      state.filtered.forEach((doc) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "docs-row docs-row--doc";
        row.dataset.docId = doc.id || doc.path;
        row.textContent = doc.path || doc.name;
        viewport.appendChild(row);
      });
      if (!state.filtered.find((item) => (item.id || item.path) === state.selected)) {
        state.selected = state.filtered[0] ? (state.filtered[0].id || state.filtered[0].path) : "";
      }
      dispatch({ list: state.filtered, selected: state.selected });
    }

    async function openDoc(docId) {
      const doc = state.docs.find((item) => (item.id || item.path) === docId);
      if (!doc) return;
      state.selected = docId;
      titleEl.textContent = doc.path || doc.name;
      previewEl.innerHTML = `<p class="empty-context">${t("view.docs.loading")}</p>`;
      try {
        const projectId = getProjectId(ctx);
        const current = await ctx.services.docs.getDoc(projectId, doc.path || doc.id);
        previewEl.innerHTML = renderDocContent(current.content || "", doc.path || doc.id);
        previewEl.querySelectorAll("pre code").forEach((block) => window.hljs?.highlightElement?.(block));
        dispatch({ list: state.filtered, current });
      } catch (error) {
        previewEl.innerHTML = `<p class="empty-context">${t("view.docs.previewFailed", "", { message: escapeHtml(error.message) })}</p>`;
      }
    }

    async function loadDocs() {
      const projectId = getProjectId(ctx);
      if (!projectId) {
        metaEl.textContent = t("view.docs.selectProject");
        viewport.innerHTML = `<p class="empty-context">${t("view.docs.emptyProject")}</p>`;
        previewEl.innerHTML = `<p class="empty-context">${t("view.docs.emptySelection")}</p>`;
        return;
      }
      state.docs = await ctx.services.docs.listDocs(projectId);
      applyFilter();
      if (state.selected) {
        await openDoc(state.selected);
      }
    }

    const onViewportClick = (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      const row = target.closest("[data-doc-id]");
      if (!row) return;
      void openDoc(row.dataset.docId || "");
    };

    viewport?.addEventListener("click", onViewportClick);
    filterInput?.addEventListener("input", applyFilter);
    const onRefresh = () => void loadDocs();
    refreshBtn?.addEventListener("click", onRefresh);

    ctx.__docsCleanup = () => {
      viewport?.removeEventListener("click", onViewportClick);
      filterInput?.removeEventListener("input", applyFilter);
      refreshBtn?.removeEventListener("click", onRefresh);
    };

    ctx.__docsLoad = loadDocs;
  },
  unmount() {
    this.__docsCleanup?.();
    this.__docsCleanup = null;
    this.__docsLoad = null;
  },
  onRoute: async () => {
    await DOCS_VIEW.__docsLoad?.();
  },
};
