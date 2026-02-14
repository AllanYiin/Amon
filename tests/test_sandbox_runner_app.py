import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon_sandbox_runner.app import create_app
from amon_sandbox_runner.config import RunnerSettings


class SandboxRunnerAppTests(unittest.TestCase):
    def test_run_requires_api_key_when_configured(self) -> None:
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi testclient not installed")

        app = create_app(RunnerSettings(api_key="secret"))
        client = TestClient(app)
        payload = {"language": "python", "code": "print('ok')", "timeout_s": 5, "input_files": []}

        res = client.post("/run", json=payload)
        self.assertEqual(res.status_code, 401)

        res2 = client.post("/run", json=payload, headers={"Authorization": "Bearer secret"})
        self.assertNotEqual(res2.status_code, 401)


if __name__ == "__main__":
    unittest.main()
