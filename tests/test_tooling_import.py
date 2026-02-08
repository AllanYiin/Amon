import unittest


class ToolingImportTests(unittest.TestCase):
    def test_imports_types_module(self) -> None:
        from amon.tooling import types  # noqa: WPS433

        self.assertTrue(hasattr(types, "ToolSpec"))


if __name__ == "__main__":
    unittest.main()
