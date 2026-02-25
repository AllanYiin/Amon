import unittest
from unittest.mock import patch

from amon.ui_server import AmonThreadingHTTPServer


class UIHandlerConnectionResetTests(unittest.TestCase):
    def test_server_handle_error_suppresses_connection_reset_traceback(self) -> None:
        server = object.__new__(AmonThreadingHTTPServer)

        with patch("amon.ui_server.sys.exc_info", return_value=(ConnectionResetError, ConnectionResetError("reset"), None)):
            with patch("amon.ui_server.log_event") as log_event_mock:
                with patch("http.server.ThreadingHTTPServer.handle_error") as base_handle_error:
                    AmonThreadingHTTPServer.handle_error(server, request=None, client_address=("127.0.0.1", 12345))

        log_event_mock.assert_called_once()
        base_handle_error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
