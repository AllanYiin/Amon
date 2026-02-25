import unittest
from http.server import SimpleHTTPRequestHandler
from unittest.mock import patch

from amon.ui_server import AmonUIHandler


class UIHandlerConnectionResetTests(unittest.TestCase):
    def test_handle_one_request_connection_reset_logs_and_closes(self) -> None:
        handler = object.__new__(AmonUIHandler)
        handler.client_address = ("127.0.0.1", 12345)
        handler.close_connection = False

        with patch.object(SimpleHTTPRequestHandler, "handle_one_request", side_effect=ConnectionResetError("reset")):
            with patch("amon.ui_server.log_event") as log_event_mock:
                AmonUIHandler.handle_one_request(handler)

        self.assertTrue(handler.close_connection)
        log_event_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
