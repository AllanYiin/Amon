from pathlib import Path
import unittest


class UIEventStreamClientRegistryTests(unittest.TestCase):
    def test_sse_registry_includes_update_event_names(self) -> None:
        content = Path("src/amon/ui/event_stream_client.js").read_text(encoding="utf-8")
        self.assertIn('"run.update"', content)
        self.assertIn('"job.update"', content)
        self.assertIn('"billing.update"', content)
        self.assertIn('"docs.update"', content)


if __name__ == "__main__":
    unittest.main()
