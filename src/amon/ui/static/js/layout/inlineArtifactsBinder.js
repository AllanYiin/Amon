function clearInlineRows(container) {
  container?.querySelectorAll('[data-inline-artifact-row="true"]').forEach((node) => node.remove());
}

function activateInlinePreview(elements, item) {
  if (!elements?.artifactsInlinePreviewFrame || !item?.url) return;
  elements.artifactsInlinePreview.hidden = false;
  elements.artifactsInlinePreviewTitle.textContent = item.name || item.title || "inline artifact";
  elements.artifactsInlinePreviewFrame.src = item.url;
  elements.artifactsPreviewOpenTab.onclick = () => window.open(item.url, "_blank", "noopener");
  elements.artifactsPreviewRefresh.onclick = () => {
    elements.artifactsInlinePreviewFrame.src = item.url;
  };
}

export function renderInlineArtifactsList(elements, inlineArtifacts = []) {
  if (!elements?.artifactsInspectorList) return;
  clearInlineRows(elements.artifactsInspectorList);

  inlineArtifacts.forEach((artifact) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "list-row list-row--clickable";
    row.dataset.inlineArtifactRow = "true";
    row.textContent = `[inline] ${artifact.name || artifact.title || "artifact"}`;
    row.addEventListener("click", () => activateInlinePreview(elements, artifact));
    elements.artifactsInspectorList.prepend(row);
  });
}

export function renderInlineArtifactStreamingHint(elements, text = "") {
  const host = elements?.artifactsInlineStreamingHint || elements?.artifactsOverview?.parentElement;
  if (!host) return;

  let hint = elements?.artifactsInlineStreamingHint || document.getElementById("artifacts-inline-streaming-hint");
  if (!hint) {
    hint = document.createElement("div");
    hint.id = "artifacts-inline-streaming-hint";
    hint.className = "context-overview muted";
    host.insertBefore(hint, elements?.artifactsInlinePreview || null);
  }
  hint.textContent = text || "";
  hint.hidden = !text;
}

export function showInlineArtifactPreview(elements, item) {
  activateInlinePreview(elements, item);
}
