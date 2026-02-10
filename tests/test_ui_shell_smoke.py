from pathlib import Path
import unittest


class UIShellSmokeTests(unittest.TestCase):
    def test_index_contains_ui_shell_scaffold(self) -> None:
        html = Path("src/amon/ui/index.html").read_text(encoding="utf-8")

        for token in [
            "shell-sidebar",
            "toggle-context-panel",
            "Memory Used",
            "Tools &amp; Skills",
            "Daemon：Healthy",
        ]:
            self.assertIn(token, html)


if __name__ == "__main__":
    unittest.main()
