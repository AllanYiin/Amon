import errno
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.fs.atomic import atomic_write_text


def _permission_error(winerror: int) -> PermissionError:
    error = PermissionError(errno.EACCES, "Access denied")
    error.winerror = winerror
    return error


class FsAtomicTests(unittest.TestCase):
    def test_atomic_write_text_retries_transient_replace_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "index.json"
            path.write_text('{"threads":[]}\n', encoding="utf-8")
            real_replace = os.replace
            calls: list[tuple[str, str]] = []

            def flaky_replace(source: str, destination: Path) -> None:
                calls.append((str(source), str(destination)))
                if len(calls) == 1:
                    raise _permission_error(5)
                real_replace(source, destination)

            with patch("amon.fs.atomic.os.replace", side_effect=flaky_replace), patch(
                "amon.fs.atomic.time.sleep"
            ) as mocked_sleep:
                atomic_write_text(path, '{"threads":[{"id":"t1"}]}\n')

            self.assertEqual(path.read_text(encoding="utf-8"), '{"threads":[{"id":"t1"}]}\n')
            self.assertEqual(len(calls), 2)
            mocked_sleep.assert_called_once()

    def test_atomic_write_text_removes_temp_file_after_permanent_replace_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "index.json"

            with patch("amon.fs.atomic.os.replace", side_effect=PermissionError(errno.EACCES, "Denied")):
                with self.assertRaises(PermissionError):
                    atomic_write_text(path, '{"threads":[]}\n')

            leaked_temp_files = list(path.parent.glob(f".{path.name}.*.tmp"))
            self.assertEqual(leaked_temp_files, [])


if __name__ == "__main__":
    unittest.main()
