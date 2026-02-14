import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.sandbox.client import (  # noqa: E402
    SandboxHTTPError,
    SandboxProtocolError,
    SandboxRunnerClient,
    SandboxRunnerSettings,
    SandboxTimeoutError,
    build_input_file,
    decode_output_files,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._payload


class SandboxRunnerClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SandboxRunnerSettings(
            base_url="http://runner.local:8088",
            timeout_s=15,
            api_key_env=None,
            limits={},
            features={},
        )

    def test_run_code_builds_request_with_input_files(self) -> None:
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(req.header_items())
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeResponse(
                {
                    "id": "run-1",
                    "exit_code": 0,
                    "stdout": "ok",
                    "stderr": "",
                    "duration_ms": 10,
                    "timed_out": False,
                    "output_files": [],
                }
            )

        client = SandboxRunnerClient(self.settings)
        input_files = [build_input_file("data/input.txt", b"hello")]

        with patch("amon.sandbox.client.request.urlopen", side_effect=fake_urlopen):
            response = client.run_code(language="python", code="print('ok')", input_files=input_files)

        self.assertEqual(response["exit_code"], 0)
        self.assertEqual(captured["url"], "http://runner.local:8088/run")
        self.assertEqual(captured["timeout"], 15)
        self.assertEqual(captured["payload"]["input_files"], input_files)
        self.assertEqual(captured["payload"]["language"], "python")
        self.assertTrue(captured["payload"]["request_id"])

    def test_run_code_attaches_api_key_header(self) -> None:
        captured = {}

        def fake_urlopen(req, timeout):
            captured["headers"] = dict(req.header_items())
            return _FakeResponse(
                {
                    "id": "run-1",
                    "exit_code": 0,
                    "stdout": "ok",
                    "stderr": "",
                    "duration_ms": 10,
                    "timed_out": False,
                    "output_files": [],
                }
            )

        settings = SandboxRunnerSettings(
            base_url="http://runner.local:8088",
            timeout_s=15,
            api_key_env="SANDBOX_RUNNER_API_KEY",
            limits={},
            features={},
        )
        client = SandboxRunnerClient(settings)

        with patch.dict("os.environ", {"SANDBOX_RUNNER_API_KEY": "token-123"}, clear=False):
            with patch("amon.sandbox.client.request.urlopen", side_effect=fake_urlopen):
                client.run_code(language="python", code="print('ok')")

        self.assertEqual(captured["headers"].get("Authorization"), "Bearer token-123")

    def test_run_code_handles_http_500(self) -> None:
        http_error = error.HTTPError(
            url="http://runner.local:8088/run",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"internal"}'),
        )

        client = SandboxRunnerClient(self.settings)
        with patch("amon.sandbox.client.request.urlopen", side_effect=http_error):
            with self.assertRaises(SandboxHTTPError):
                client.run_code(language="python", code="print('x')")

    def test_run_code_handles_timeout(self) -> None:
        client = SandboxRunnerClient(self.settings)
        with patch("amon.sandbox.client.request.urlopen", side_effect=socket.timeout()):
            with self.assertRaises(SandboxTimeoutError):
                client.run_code(language="python", code="print('x')")

    def test_run_code_rejects_invalid_response(self) -> None:
        class _InvalidResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"not-json"

        client = SandboxRunnerClient(self.settings)
        with patch("amon.sandbox.client.request.urlopen", return_value=_InvalidResponse()):
            with self.assertRaises(SandboxProtocolError):
                client.run_code(language="python", code="print('x')")

    def test_decode_output_files_and_path_safety(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            files = [
                {"path": "result/output.txt", "content_b64": "aGVsbG8="},
            ]
            written = decode_output_files(files, out_dir)
            self.assertEqual((out_dir / "result" / "output.txt").read_text(encoding="utf-8"), "hello")
            self.assertEqual(len(written), 1)

            with self.assertRaises(SandboxProtocolError):
                decode_output_files([{"path": "../escape.txt", "content_b64": "aGVsbG8="}], out_dir)


if __name__ == "__main__":
    unittest.main()
