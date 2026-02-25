import unittest
from unittest.mock import patch

from amon.ui_server import AmonUIHandler


class _ConnectionResetReader:
    def readline(self, _size: int = -1) -> bytes:
        raise ConnectionResetError("reset")


class UIHandlerConnectionResetTests(unittest.TestCase):
    def test_handle_one_request_connection_reset_logs_and_closes(self) -> None:
        handler = object.__new__(AmonUIHandler)
        handler.client_address = ("127.0.0.1", 12345)
        handler.close_connection = False
        handler.rfile = _ConnectionResetReader()
        handler.wfile = None

        with patch("amon.ui_server.log_event") as log_event_mock:
            AmonUIHandler.handle_one_request(handler)

        self.assertTrue(handler.close_connection)
        log_event_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
