function escapeHtml(text = "") {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function scriptSafeText(text = "") {
  return String(text || "").replaceAll("</script", "<\\/script");
}

function pickHtmlEntry(files = new Map()) {
  const htmlFiles = Array.from(files.values()).filter((item) => /\.html?$/i.test(item.filename || ""));
  if (!htmlFiles.length) return null;
  return htmlFiles.find((item) => String(item.filename || "").toLowerCase() === "index.html") || htmlFiles[0];
}

function getReferencedFiles(html = "", files = [], kind = "css") {
  return files.filter((file) => {
    const name = String(file.filename || "");
    if (!name) return false;
    if (kind === "css") {
      const pattern = new RegExp(`<link[^>]+href=["'][^"']*${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}["'][^>]*>`, "i");
      return pattern.test(html);
    }
    const pattern = new RegExp(`<script[^>]+src=["'][^"']*${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}["'][^>]*>\\s*</script>`, "i");
    return pattern.test(html);
  });
}

function injectCssAndJs(htmlEntry, filesMap) {
  let html = String(htmlEntry.content || "");
  const allFiles = Array.from(filesMap.values()).filter((item) => item.filename !== htmlEntry.filename);
  const cssFiles = allFiles.filter((item) => /\.css$/i.test(item.filename || ""));
  const jsFiles = allFiles.filter((item) => /\.js$/i.test(item.filename || ""));

  const referencedCss = getReferencedFiles(html, cssFiles, "css");
  if (referencedCss.length) {
    const styleText = referencedCss.map((file) => `/* ${file.filename} */\n${file.content || ""}`).join("\n\n");
    const styleTag = `<style data-inline-artifact="bundle">\n${styleText}\n</style>`;
    html = html.includes("</head>") ? html.replace("</head>", `${styleTag}\n</head>`) : `${styleTag}\n${html}`;
  }

  const referencedJs = getReferencedFiles(html, jsFiles, "js");
  if (referencedJs.length) {
    const scriptText = referencedJs
      .map((file) => `/* ${file.filename} */\n${scriptSafeText(file.content || "")}`)
      .join("\n\n");
    const scriptTag = `<script data-inline-artifact="bundle">\n${scriptText}\n</script>`;
    html = html.includes("</body>") ? html.replace("</body>", `${scriptTag}\n</body>`) : `${html}\n${scriptTag}`;
  }

  return html;
}

export function buildPreviewForFiles(files = new Map()) {
  const htmlEntry = pickHtmlEntry(files);
  if (htmlEntry) {
    const html = injectCssAndJs(htmlEntry, files);
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    return {
      kind: "url",
      url: URL.createObjectURL(blob),
      title: htmlEntry.filename,
    };
  }

  const fallbackBody = Array.from(files.values())
    .map((file) => `### ${file.filename}\n\n${file.content || ""}`)
    .join("\n\n");

  const shell = `<!doctype html><html><head><meta charset="utf-8"><title>Inline Artifact Preview</title></head><body><pre>${escapeHtml(fallbackBody || "尚無可預覽內容")}</pre></body></html>`;
  const blob = new Blob([shell], { type: "text/html;charset=utf-8" });
  return {
    kind: "url",
    url: URL.createObjectURL(blob),
    title: "inline-artifact-preview.html",
  };
}

export function revoke(url) {
  if (!url || typeof URL === "undefined" || typeof URL.revokeObjectURL !== "function") return;
  try {
    URL.revokeObjectURL(url);
  } catch (error) {
    console.warn("inline_artifact_revoke_failed", error);
  }
}
