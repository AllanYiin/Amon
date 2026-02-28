import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from amon.ui_server import AmonThreadingHTTPServer, AmonUIHandler


class _BrokenStream:
    def write(self, _: bytes) -> int:
        raise ConnectionAbortedError("aborted")

    def flush(self) -> None:
        return None


class UIHandlerConnectionResetTests(unittest.TestCase):
    def test_server_handle_error_suppresses_connection_reset_traceback(self) -> None:
        server = object.__new__(AmonThreadingHTTPServer)

        with patch("amon.ui_server.sys.exc_info", return_value=(ConnectionResetError, ConnectionResetError("reset"), None)):
            with patch("amon.ui_server.log_event") as log_event_mock:
                with patch("http.server.ThreadingHTTPServer.handle_error") as base_handle_error:
                    AmonThreadingHTTPServer.handle_error(server, request=None, client_address=("127.0.0.1", 12345))

        log_event_mock.assert_called_once()
        base_handle_error.assert_not_called()


    def test_server_handle_error_suppresses_connection_aborted_traceback(self) -> None:
        server = object.__new__(AmonThreadingHTTPServer)

        with patch("amon.ui_server.sys.exc_info", return_value=(ConnectionAbortedError, ConnectionAbortedError("aborted"), None)):
            with patch("amon.ui_server.log_event") as log_event_mock:
                with patch("http.server.ThreadingHTTPServer.handle_error") as base_handle_error:
                    AmonThreadingHTTPServer.handle_error(server, request=None, client_address=("127.0.0.1", 12345))

        log_event_mock.assert_called_once()
        base_handle_error.assert_not_called()

    def test_chat_stream_disconnect_is_logged_without_error_event(self) -> None:
        handler = object.__new__(AmonUIHandler)
        handler.core = Mock()
        handler.wfile = _BrokenStream()
        handler.client_address = ("127.0.0.1", 9000)
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()

        parsed = SimpleNamespace(query="message=%E4%BD%A0%E5%A5%BD")
        with patch("amon.ui_server.log_event") as log_event_mock:
            handler._handle_chat_stream(parsed)

        events = [call.args[0].get("event") for call in log_event_mock.call_args_list if call.args]
        self.assertIn("ui_chat_stream_received", events)
        self.assertIn("ui_client_disconnected", events)
        self.assertNotIn("ui_chat_stream_error", events)


if __name__ == "__main__":
    unittest.main()
