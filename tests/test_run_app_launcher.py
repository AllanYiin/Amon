from pathlib import Path
import unittest


class RunAppLauncherTests(unittest.TestCase):
    def test_windows_launcher_starts_ui_server_and_opens_http_entrypoint(self) -> None:
        launcher = Path("run_app.bat").read_text(encoding="utf-8")

        for token in [
            'set "PYTHONPATH=%ROOT_DIR%src"',
            'set "AMON_UI_PORT=8000"',
            'set "AMON_UI_URL=http://127.0.0.1:%AMON_UI_PORT%/#/chat"',
            '"%PYTHON_EXE%" -m amon.cli ui --port %AMON_UI_PORT%',
            'Invoke-WebRequest -UseBasicParsing',
            'start "" "%AMON_UI_URL%"',
            'logs\\run_app.log',
        ]:
            self.assertIn(token, launcher)

        self.assertNotIn("index.html", launcher)
        self.assertNotIn("file://", launcher)


if __name__ == "__main__":
    unittest.main()
