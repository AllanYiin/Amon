import tempfile
import unittest
from pathlib import Path

from tools.scan_unicode_controls import iter_text_files, scan_file


class ScanUnicodeControlsTests(unittest.TestCase):
    def test_iter_text_files_skips_minified_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            minified = root / "vendor.min.js"
            regular = root / "app.js"
            minified.write_text("console.log('x');", encoding="utf-8")
            regular.write_text("console.log('y');", encoding="utf-8")

            paths = list(iter_text_files(root, exclude=set()))

            self.assertEqual(paths, [regular])

    def test_scan_file_finds_zero_width_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "sample.txt"
            target.write_text("A\u200BB\n", encoding="utf-8")

            findings = scan_file(target, include_zero_width=True)

            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].codepoint, "U+200B")


if __name__ == "__main__":
    unittest.main()
