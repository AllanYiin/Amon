function ensureSvgNamespace(svgMarkup) {
  const withSvgNs = svgMarkup.includes("xmlns=")
    ? svgMarkup
    : svgMarkup.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"');
  return withSvgNs.includes("xmlns:xlink=")
    ? withSvgNs
    : withSvgNs.replace("<svg", '<svg xmlns:xlink="http://www.w3.org/1999/xlink"');
}

function ensureSvgSize(svgMarkup, svgEl) {
  const hasWidth = /\swidth\s*=/.test(svgMarkup);
  const hasHeight = /\sheight\s*=/.test(svgMarkup);
  if (hasWidth && hasHeight) return svgMarkup;

  const widthAttr = String(svgEl.getAttribute("width") || "").trim();
  const heightAttr = String(svgEl.getAttribute("height") || "").trim();
  if (widthAttr && heightAttr) {
    const nextWithWidth = hasWidth ? svgMarkup : svgMarkup.replace("<svg", `<svg width="${widthAttr}"`);
    return hasHeight ? nextWithWidth : nextWithWidth.replace("<svg", `<svg height="${heightAttr}"`);
  }

  const viewBox = String(svgEl.getAttribute("viewBox") || "").trim();
  if (!viewBox) return svgMarkup;
  const [, , width, height] = viewBox.split(/\s+/);
  const safeWidth = Number(width);
  const safeHeight = Number(height);
  const fallbackWidth = Number.isFinite(safeWidth) && safeWidth > 0 ? safeWidth : 800;
  const fallbackHeight = Number.isFinite(safeHeight) && safeHeight > 0 ? safeHeight : 600;
  const nextWithWidth = hasWidth ? svgMarkup : svgMarkup.replace("<svg", `<svg width="${fallbackWidth}"`);
  return hasHeight ? nextWithWidth : nextWithWidth.replace("<svg", `<svg height="${fallbackHeight}"`);
}

export function buildExportableSvg(svgEl) {
  if (!(svgEl instanceof SVGElement)) return "";
  const rawSvg = String(svgEl.outerHTML || "").trim();
  if (!rawSvg) return "";
  const withNamespaces = ensureSvgNamespace(rawSvg);
  const withSize = ensureSvgSize(withNamespaces, svgEl);
  return `<?xml version="1.0" encoding="UTF-8"?>\n${withSize}\n`;
}

export function downloadTextFile(filename, content, mimeType = "text/plain;charset=utf-8") {
  const safeFilename = String(filename || "").trim();
  const value = String(content || "");
  if (!safeFilename || !value) return false;
  const blob = new Blob([value], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = safeFilename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return true;
}
