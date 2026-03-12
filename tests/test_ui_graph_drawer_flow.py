from pathlib import Path
import unittest


class GraphDrawerFlowContractTests(unittest.TestCase):
    def test_graph_view_wires_single_select_node_path_for_list_and_canvas(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("async function selectNode(nodeId, options = {})", graph_js)
        self.assertIn("void selectNode(node.dataset.nodeId || \"\")", graph_js)
        self.assertIn("function renderGraphCanvas(viewModel)", graph_js)
        self.assertIn("void selectNode(nodeId)", graph_js)

    def test_graph_view_supports_drawer_open_close_controls(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("function openGraphNodeDrawer()", graph_js)
        self.assertIn("function closeGraphNodeDrawer()", graph_js)
        self.assertIn("event.key !== \"Escape\"", graph_js)
        self.assertIn("target.closest(\"#graph-node-drawer\")", graph_js)
        self.assertIn("drawerCloseEl?.addEventListener(\"click\", onDrawerClose)", graph_js)

    def test_graph_view_has_live_refresh_subscription_and_throttle(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("function subscribeGraphLiveUpdates()", graph_js)
        self.assertIn("function unsubscribeGraphLiveUpdates()", graph_js)
        self.assertIn("function scheduleRefresh(kind = \"runListOnly\")", graph_js)
        self.assertIn("REFRESH_THROTTLE_MS", graph_js)
        self.assertIn("ctx.bus?.on?.(\"stream:event\"", graph_js)


    def test_graph_view_has_auto_focus_and_exportable_svg_path(self) -> None:
        graph_js = Path("src/amon/ui/static/js/views/graph.js").read_text(encoding="utf-8")
        self.assertIn("function syncAutoFocus(viewModel)", graph_js)
        self.assertIn("function buildGraphCanvasSvg(layoutModel)", graph_js)
        self.assertIn("preferredFocusNodeId", graph_js)

    def test_bootstrap_uses_adapter_status_label_without_private_mapping(self) -> None:
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")
        self.assertNotIn("function nodeStatusLabel(status)", bootstrap_js)
        self.assertIn("nodeVm.statusUi.label", bootstrap_js)

    def test_event_stream_client_registers_node_update_events(self) -> None:
        stream_js = Path("src/amon/ui/event_stream_client.js").read_text(encoding="utf-8")
        self.assertIn('"node.update"', stream_js)


if __name__ == "__main__":
    unittest.main()
