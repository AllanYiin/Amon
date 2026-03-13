from __future__ import annotations

import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.cli import build_parser  # noqa: E402


class CliGraphContractTests(unittest.TestCase):
    def test_parser_rejects_removed_graph_migrate_command(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["graph", "migrate", "--help"])


if __name__ == "__main__":
    unittest.main()
