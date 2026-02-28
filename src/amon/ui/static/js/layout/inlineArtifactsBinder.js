function clearInlineRows(container) {
  container?.querySelectorAll('[data-inline-artifact-row="true"]').forEach((node) => node.remove());
}

const INLINE_PREVIEW_SANDBOX = "allow-scripts allow-forms allow-modals";

function ensureInlinePreviewSandbox(frame) {
  if (!frame) return;
  frame.setAttribute("sandbox", INLINE_PREVIEW_SANDBOX);
}

function activateInlinePreview(elements, item) {
  const previewUrl = item?.previewUrl || item?.url;
  if (!elements?.artifactsInlinePreviewFrame || !previewUrl) return;
  ensureInlinePreviewSandbox(elements.artifactsInlinePreviewFrame);
  elements.artifactsInlinePreview.hidden = false;
  elements.artifactsInlinePreviewTitle.textContent = item.filename || item.name || item.title || "inline artifact";
  elements.artifactsInlinePreviewFrame.src = previewUrl;
  elements.artifactsPreviewOpenTab.onclick = () => window.open(previewUrl, "_blank", "noopener");
  elements.artifactsPreviewRefresh.onclick = () => {
    ensureInlinePreviewSandbox(elements.artifactsInlinePreviewFrame);
    elements.artifactsInlinePreviewFrame.src = previewUrl;
  };
}

export function renderInlineArtifactsList(elements, inlineArtifacts = []) {
  if (!elements?.artifactsInspectorList) return;
  clearInlineRows(elements.artifactsInspectorList);

  const hasInlineArtifacts = inlineArtifacts.length > 0;
  if (elements.artifactsEmpty) {
    elements.artifactsEmpty.hidden = hasInlineArtifacts;
  }

  inlineArtifacts.forEach((artifact) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "list-row list-row--clickable";
    row.dataset.inlineArtifactRow = "true";
    row.textContent = `[inline] ${artifact.filename || artifact.name || artifact.title || "artifact"}`;
    row.addEventListener("click", () => activateInlinePreview(elements, artifact));
    elements.artifactsInspectorList.append(row);
  });
}

export function renderInlineArtifactStreamingHint(elements, text = "") {
  const host = elements?.artifactsOverview?.parentElement;
  if (!host) return;

  let hint = elements?.artifactsInlineStreamingHint || document.getElementById("artifacts-inline-streaming-hint");
  if (!hint) {
    hint = document.createElement("div");
    hint.id = "artifacts-inline-streaming-hint";
    hint.className = "muted";
    host.insertBefore(hint, elements?.artifactsInlinePreview || elements?.artifactsListDetails || null);
  }
  hint.textContent = text || "";
  hint.hidden = !text;
}

export function showInlineArtifactPreview(elements, item) {
  activateInlinePreview(elements, item);
}
