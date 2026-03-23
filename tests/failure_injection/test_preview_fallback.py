import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.application import PreviewService, UploadService


class PreviewFallbackFailureInjectionTests(unittest.TestCase):
    def test_pdf_preview_failure_falls_back_to_metadata_only_with_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            source = Path(tmp) / "demo.pdf"
            source.write_bytes(b"%PDF-1.4\n%stub\n")

            asset = UploadService(project_root).create_upload(source)
            payload = PreviewService(project_root).build_preview_payload(asset.id)

            self.assertEqual(asset.status, "preview_ready")
            self.assertEqual(payload["preview"]["preview_kind"], "metadata_only")
            self.assertFalse(payload["preview"]["preview_available"])
            self.assertIn("pdf", payload["preview"]["fallback_reason"])


if __name__ == "__main__":
    unittest.main()
