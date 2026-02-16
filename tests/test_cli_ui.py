from argparse import Namespace
from pathlib import Path
from unittest.mock import patch
import unittest

from amon.cli import _handle_ui


class CliUiTests(unittest.TestCase):
    def test_handle_ui_passes_data_dir_to_server(self) -> None:
        args = Namespace(port=8123, data_dir="~/amon-test-home")
        with patch("amon.ui_server.serve_ui") as serve_ui:
            _handle_ui(args)
        serve_ui.assert_called_once_with(port=8123, data_dir=Path("~/amon-test-home").expanduser())

    def test_handle_ui_without_data_dir_uses_default(self) -> None:
        args = Namespace(port=9000, data_dir=None)
        with patch("amon.ui_server.serve_ui") as serve_ui:
            _handle_ui(args)
        serve_ui.assert_called_once_with(port=9000, data_dir=None)


if __name__ == "__main__":
    unittest.main()
