import unittest
from http.server import SimpleHTTPRequestHandler
from unittest.mock import patch

from amon.ui_server import AmonUIHandler


class UIHandlerConnectionResetTests(unittest.TestCase):
    def test_handle_connection_reset_sets_close_connection(self) -> None:
        handler = object.__new__(AmonUIHandler)
        handler.client_address = ("127.0.0.1", 12345)
        handler.close_connection = False

        with patch.object(SimpleHTTPRequestHandler, "handle", side_effect=ConnectionResetError("reset")):
            with patch("amon.ui_server.log_event") as log_event_mock:
                AmonUIHandler.handle(handler)

        self.assertTrue(handler.close_connection)
        log_event_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
