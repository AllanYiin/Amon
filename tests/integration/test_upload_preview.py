import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from amon.application import PreviewService, UploadService


class UploadPreviewIntegrationTests(unittest.TestCase):
    def test_text_upload_generates_inline_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            source = Path(tmp) / "note.md"
            source.write_text("# Title\nline1\nline2\n", encoding="utf-8")

            asset = UploadService(project_root).create_upload(source)
            payload = PreviewService(project_root).build_preview_payload(asset.id)

            self.assertEqual(asset.status, "preview_ready")
            self.assertTrue(Path(asset.preview_ref or "").exists())
            self.assertEqual(payload["preview"]["preview_kind"], "inline_text")
            self.assertTrue(payload["preview"]["preview_available"])

    def test_unknown_binary_upload_falls_back_to_metadata_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp) / "workspace"
            project_root.mkdir(parents=True, exist_ok=True)
            source = Path(tmp) / "blob.bin"
            source.write_bytes(os.urandom(32))

            asset = UploadService(project_root).create_upload(source)
            payload = PreviewService(project_root).build_preview_payload(asset.id)

            self.assertEqual(asset.status, "preview_ready")
            self.assertIsNone(asset.preview_ref)
            self.assertEqual(payload["preview"]["preview_kind"], "metadata_only")
            self.assertFalse(payload["preview"]["preview_available"])


if __name__ == "__main__":
    unittest.main()
