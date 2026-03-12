from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


class IndexHtmlVendorSmokeTests(unittest.TestCase):
    def test_graph_page_uses_local_svg_pan_zoom_but_no_longer_loads_mermaid(self) -> None:
        index_html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        self.assertIn('src="static/vendor/svg-pan-zoom/svg-pan-zoom.min.js"', index_html)
        self.assertNotIn('src="static/vendor/mermaid/mermaid.min.js"', index_html)
        self.assertNotIn("cdn.jsdelivr.net/npm/mermaid", index_html)
        self.assertNotIn("cdn.jsdelivr.net/npm/svg-pan-zoom", index_html)

    def test_vendor_svg_pan_zoom_build_exports_svgPanZoom_without_svgjs_global(self) -> None:
        svg_pan_zoom_vendor_js = Path("src/amon/ui/static/vendor/svg-pan-zoom/svg-pan-zoom.min.js").read_text(encoding="utf-8")
        self.assertIn("svgPanZoom", svg_pan_zoom_vendor_js)
        self.assertNotIn("new SVG(document.createDocumentFragment())", svg_pan_zoom_vendor_js)


@unittest.skipIf(shutil.which("node") is None, "node is required for graph frontend smoke tests")
class GraphViewCustomFlowSmokeTests(unittest.TestCase):
    def test_graph_view_uses_custom_canvas_renderer_instead_of_mermaid(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("function createGraphLayout(viewModel)", graph_js)
        self.assertIn("function renderGraphCanvas(viewModel)", graph_js)
        self.assertIn("function buildGraphCanvasSvg(layoutModel)", graph_js)
        self.assertNotIn("__mermaid", graph_js)

        script = textwrap.dedent(
            """
            function buildEdgePath(sourceBox, targetBox) {
              const startX = sourceBox.x + sourceBox.width;
              const startY = sourceBox.y + sourceBox.height / 2;
              const endX = targetBox.x;
              const endY = targetBox.y + targetBox.height / 2;
              const deltaX = Math.max(72, (endX - startX) * 0.5);
              return `M ${startX} ${startY} C ${startX + deltaX} ${startY}, ${endX - deltaX} ${endY}, ${endX} ${endY}`;
            }

            const d = buildEdgePath(
              { x: 40, y: 60, width: 272, height: 188 },
              { x: 360, y: 60, width: 272, height: 188 }
            );
            console.log(JSON.stringify({ d }));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertIn("M 312 154", payload["d"])
        self.assertIn("C", payload["d"])

    def test_graph_view_does_not_store_cleanup_on_undefined_this(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("GRAPH_VIEW.__graphCleanup = () =>", graph_js)
        self.assertIn("GRAPH_VIEW.__graphLoad = load;", graph_js)
        self.assertNotIn("this.__graphCleanup = () =>", graph_js)


if __name__ == "__main__":
    unittest.main()
