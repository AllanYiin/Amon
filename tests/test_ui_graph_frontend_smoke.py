from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


class IndexHtmlVendorSmokeTests(unittest.TestCase):
    def test_mermaid_and_svg_pan_zoom_use_local_vendor_assets_without_jsdelivr(self) -> None:
        index_html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        self.assertIn('src="static/vendor/mermaid/mermaid.min.js"', index_html)
        self.assertIn('src="static/vendor/svg-pan-zoom/svg-pan-zoom.min.js"', index_html)
        self.assertNotIn("cdn.jsdelivr.net/npm/mermaid", index_html)
        self.assertNotIn("cdn.jsdelivr.net/npm/svg-pan-zoom", index_html)

    def test_vendor_mermaid_build_is_umd_bundle(self) -> None:
        mermaid_vendor_js = Path("src/amon/ui/static/vendor/mermaid/mermaid.min.js").read_text(encoding="utf-8")
        self.assertIn("JM.mermaid=Ag()", mermaid_vendor_js)
        self.assertNotIn('import {', mermaid_vendor_js)

    def test_vendor_svg_pan_zoom_build_exports_svgPanZoom_without_svgjs_global(self) -> None:
        svg_pan_zoom_vendor_js = Path("src/amon/ui/static/vendor/svg-pan-zoom/svg-pan-zoom.min.js").read_text(encoding="utf-8")
        self.assertIn("svgPanZoom", svg_pan_zoom_vendor_js)
        self.assertNotIn("new SVG(document.createDocumentFragment())", svg_pan_zoom_vendor_js)


@unittest.skipIf(shutil.which("node") is None, "node is required for graph frontend smoke tests")
class GraphViewMermaidMissingSmokeTests(unittest.TestCase):
    def test_graph_mermaid_missing_branch_renders_expected_notice_text(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn('!window.__mermaid || typeof window.__mermaid.render !== "function"', graph_js)
        self.assertIn('message: "Mermaid 未載入（可能離線或資源被擋）"', graph_js)

        script = textwrap.dedent(
            """
            class FakeElement {
              constructor() {
                this.children = [];
                this.textContent = "";
                this.className = "";
                this.dataset = {};
              }
              appendChild(child) {
                this.children.push(child);
                return child;
              }
              collectText() {
                let text = this.textContent || "";
                for (const child of this.children) {
                  if (typeof child.collectText === "function") text += child.collectText();
                }
                return text;
              }
            }

            const previewEl = new FakeElement();
            const document = { createElement: () => new FakeElement() };
            const window = { __mermaid: undefined };

            function renderGraphPreviewNotice({ message, detail = "" }) {
              const noticeEl = document.createElement("p");
              noticeEl.className = "graph-empty-state graph-empty-state--warning";
              const messageEl = document.createElement("span");
              messageEl.textContent = message;
              noticeEl.appendChild(messageEl);
              if (detail) {
                const detailEl = document.createElement("small");
                detailEl.textContent = detail;
                noticeEl.appendChild(detailEl);
              }
              previewEl.appendChild(noticeEl);
            }

            if (!window.__mermaid || typeof window.__mermaid?.render !== "function") {
              renderGraphPreviewNotice({
                message: "Mermaid 未載入（可能離線或資源被擋）",
                detail: "請嘗試重新整理頁面後再試一次。",
              });
            }

            console.log(JSON.stringify({ previewText: previewEl.collectText() }));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        self.assertIn("Mermaid 未載入", payload["previewText"])

    def test_graph_view_does_not_store_cleanup_on_undefined_this(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("GRAPH_VIEW.__graphCleanup = () =>", graph_js)
        self.assertIn("GRAPH_VIEW.__graphLoad = load;", graph_js)
        self.assertNotIn("this.__graphCleanup = () =>", graph_js)


if __name__ == "__main__":
    unittest.main()
