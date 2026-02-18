import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORT_SCAN_DIRS = (ROOT / "src", ROOT / "tests")
REQUIREMENTS_FILE = ROOT / "requirements.txt"

# import 名稱 -> requirements.txt 套件名稱
THIRD_PARTY_IMPORT_MAP = {
    "yaml": "PyYAML",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
}

# 專案內部模組，不應出現在 requirements.txt
LOCAL_MODULES = {"amon", "amon_sandbox_runner"}


def _collect_top_level_imports() -> set[str]:
    modules: set[str] = set()
    for base in IMPORT_SCAN_DIRS:
        for py_file in base.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        modules.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    modules.add(node.module.split(".")[0])
    return modules


def _parse_requirement_names() -> set[str]:
    names: set[str] = set()
    for raw_line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = line.split(";", 1)[0].strip()
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if sep in requirement:
                requirement = requirement.split(sep, 1)[0].strip()
                break
        if requirement:
            names.add(requirement.lower())
    return names


class RequirementsSyncTests(unittest.TestCase):
    def test_requirements_cover_all_third_party_imports(self) -> None:
        imports = _collect_top_level_imports()
        stdlib = set(sys.stdlib_module_names)

        third_party_imports = {
            module
            for module in imports
            if module not in stdlib
            and module not in LOCAL_MODULES
            and module != "__future__"
        }

        expected_packages = {
            THIRD_PARTY_IMPORT_MAP.get(module, module).lower()
            for module in third_party_imports
        }
        actual_packages = _parse_requirement_names()

        missing = sorted(expected_packages - actual_packages)
        self.assertFalse(
            missing,
            f"requirements.txt 缺少第三方依賴：{', '.join(missing)}",
        )


if __name__ == "__main__":
    unittest.main()
