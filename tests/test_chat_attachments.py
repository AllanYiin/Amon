import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.chat.attachments import save_attachment
from amon.cli import build_parser


class ChatAttachmentTests(unittest.TestCase):
    def test_save_attachment_writes_file_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "project"
            project_path.mkdir(parents=True, exist_ok=True)
            source = Path(temp_dir) / "demo.txt"
            source.write_text("hello attachment", encoding="utf-8")

            manifest = save_attachment(project_path, "chat123", source)

            inbox_file = project_path / "docs" / "inbox" / "chat123" / "demo.txt"
            self.assertTrue(inbox_file.exists())
            self.assertEqual(inbox_file.read_text(encoding="utf-8"), "hello attachment")
            self.assertEqual(manifest["chat_id"], "chat123")
            self.assertEqual(len(manifest["entries"]), 1)
            entry = manifest["entries"][0]
            self.assertEqual(entry["filename"], "demo.txt")
            self.assertEqual(entry["original_name"], "demo.txt")
            self.assertEqual(entry["path"], "docs/inbox/chat123/demo.txt")
            self.assertEqual(entry["size"], len("hello attachment".encode("utf-8")))
            self.assertEqual(entry["sha256"], hashlib.sha256(b"hello attachment").hexdigest())
            self.assertTrue(entry["ts"])

            manifest_path = project_path / "docs" / "inbox" / "chat123" / "manifest.json"
            self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8")), manifest)

    def test_save_attachment_appends_manifest_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "project"
            project_path.mkdir(parents=True, exist_ok=True)
            first = Path(temp_dir) / "first.txt"
            second = Path(temp_dir) / "second.txt"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")

            save_attachment(project_path, "chat1", first)
            manifest = save_attachment(project_path, "chat1", second, target_name="renamed.txt")

            self.assertEqual(len(manifest["entries"]), 2)
            self.assertEqual(manifest["entries"][1]["filename"], "renamed.txt")
            self.assertEqual(manifest["entries"][1]["original_name"], "second.txt")

    def test_save_attachment_rejects_path_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "project"
            project_path.mkdir(parents=True, exist_ok=True)
            source = Path(temp_dir) / "ok.txt"
            source.write_text("data", encoding="utf-8")

            with self.assertRaises(ValueError):
                save_attachment(project_path, "chat1", source, target_name="../bad.txt")


class ChatAttachCliParserTests(unittest.TestCase):
    def test_build_parser_supports_chat_attach(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["chat", "attach", "--project", "proj1", "--chat-id", "chat1", "--file", "demo.txt"]
        )
        self.assertEqual(args.command, "chat")
        self.assertEqual(args.chat_command, "attach")
        self.assertEqual(args.project, "proj1")
        self.assertEqual(args.chat_id, "chat1")
        self.assertEqual(args.file, "demo.txt")


if __name__ == "__main__":
    unittest.main()
