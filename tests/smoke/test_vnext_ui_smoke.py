import unittest
from pathlib import Path


class VNextUiSmokeTests(unittest.TestCase):
    def test_workspace_view_is_wired_into_shell_and_bootstrap(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")
        shell_js = Path("src/amon/ui/static/js/views/shell.js").read_text(encoding="utf-8")
        bootstrap_js = Path("src/amon/ui/static/js/bootstrap.js").read_text(encoding="utf-8")
        workspace_js = Path("src/amon/ui/static/js/views/workspace.js").read_text(encoding="utf-8")
        services_js = Path("src/amon/ui/static/js/domain/services.js").read_text(encoding="utf-8")

        self.assertIn('data-route="workspace"', html)
        self.assertIn('id="workspace-page"', html)
        self.assertIn('workspace: "workspace"', shell_js)
        self.assertIn('elements.workspacePage.hidden = view !== "workspace";', shell_js)
        self.assertIn('import { WORKSPACE_VIEW } from "./views/workspace.js";', bootstrap_js)
        self.assertIn("WORKSPACE_VIEW", bootstrap_js)
        self.assertIn("createWorkspaceService", services_js)
        self.assertIn('id: "workspace"', workspace_js)
        self.assertIn("streamRun(", workspace_js)
        self.assertIn("approveConfirmation", workspace_js)
        self.assertIn("getUploadPreview", workspace_js)
