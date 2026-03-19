import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = ROOT / "pyproject.toml"
REQUIREMENTS_FILE = ROOT / "requirements.txt"


def _read_pyproject_dependencies() -> set[str]:
    content = PYPROJECT_FILE.read_text(encoding="utf-8")
    if tomllib is not None:
        pyproject = tomllib.loads(content)
        return set(pyproject.get("project", {}).get("dependencies", []))
    return _read_pyproject_dependencies_fallback(content)


def _read_pyproject_dependencies_fallback(content: str) -> set[str]:
    dependencies = set()
    in_dependencies = False
    for raw_line in content.splitlines():
        line = raw_line.strip().rstrip(",")
        if not in_dependencies:
            if line == "dependencies = [":
                in_dependencies = True
            continue
        if line == "]":
            break
        if not line or line.startswith("#"):
            continue
        if line.startswith('"') and line.endswith('"'):
            dependencies.add(line[1:-1])
    return dependencies


def _read_requirements_lines() -> set[str]:
    return {
        line.strip()
        for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


class RequirementsSyncTests(unittest.TestCase):
    def test_requirements_txt_matches_pyproject_dependencies(self) -> None:
        self.assertTrue(REQUIREMENTS_FILE.exists(), "requirements.txt is missing")

        dependencies = _read_pyproject_dependencies()
        requirements = _read_requirements_lines()

        missing = sorted(dependencies - requirements)
        extra = sorted(requirements - dependencies)

        message = []
        if missing:
            message.append(f"Missing: {missing}")
        if extra:
            message.append(f"Extra: {extra}")

        self.assertFalse(
            missing or extra,
            "requirements.txt does not match pyproject.toml. " + "; ".join(message),
        )


if __name__ == "__main__":
    unittest.main()
