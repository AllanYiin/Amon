import unittest
from unittest.mock import patch

from amon.tooling.builtins.web import WebPolicy, handle_web_fetch
from amon.tooling.types import ToolCall


class _FakeHTTPResponse:
    status = 200

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, _max_bytes: int) -> bytes:
        return self._payload


class WebFetchTests(unittest.TestCase):
    def test_web_fetch_rejects_non_http_url(self) -> None:
        call = ToolCall(tool="web.fetch", args={"url": "string"})

        result = handle_web_fetch(call, policy=WebPolicy())

        self.assertTrue(result.is_error)
        self.assertEqual(result.meta.get("status"), "invalid_args")
        self.assertIn("http/https", result.as_text())

    def test_web_fetch_success(self) -> None:
        call = ToolCall(tool="web.fetch", args={"url": "https://example.com", "method": "GET"})

        with patch(
            "amon.tooling.builtins.web.request.urlopen",
            return_value=_FakeHTTPResponse("ok".encode("utf-8")),
        ):
            result = handle_web_fetch(call, policy=WebPolicy())

        self.assertFalse(result.is_error)
        self.assertEqual(result.as_text(), "ok")
        self.assertEqual(result.meta.get("status"), 200)


if __name__ == "__main__":
    unittest.main()
