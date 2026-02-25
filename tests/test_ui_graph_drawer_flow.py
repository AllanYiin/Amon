from pathlib import Path
import unittest


class GraphDrawerFlowContractTests(unittest.TestCase):
    def test_graph_view_wires_single_select_node_path_for_list_and_svg(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("async function selectNode(nodeId)", graph_js)
        self.assertIn("void selectNode(node.dataset.nodeId || \"\")", graph_js)
        self.assertIn("bindMermaidNodeClick", graph_js)
        self.assertIn("void selectNode(nodeId)", graph_js)

    def test_graph_view_supports_drawer_open_close_controls(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("function openGraphNodeDrawer()", graph_js)
        self.assertIn("function closeGraphNodeDrawer()", graph_js)
        self.assertIn("event.key !== \"Escape\"", graph_js)
        self.assertIn("target.closest(\"#graph-node-drawer\")", graph_js)
        self.assertIn("drawerCloseEl?.addEventListener(\"click\", onDrawerClose)", graph_js)


if __name__ == "__main__":
    unittest.main()
