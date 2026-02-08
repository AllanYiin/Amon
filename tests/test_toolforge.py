import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from amon import cli
from amon.core import AmonCore
from amon.tooling.native import parse_native_manifest


def _write_sample_tool(tool_dir: Path, name: str = "sample", risk: str = "low") -> None:
    tool_yaml = {
        "name": name,
        "version": "0.1.0",
        "description": f"{name} tool",
        "risk": risk,
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
        "default_permission": "allow" if risk != "high" else "ask",
    }
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "tool.yaml").write_text(
        yaml.safe_dump(tool_yaml, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (tool_dir / "tool.py").write_text(
        f'''from amon.tooling.types import ToolCall, ToolResult, ToolSpec

TOOL_SPEC = ToolSpec(
    name="native:{name}",
    description="{name} tool",
    input_schema={tool_yaml["input_schema"]},
    output_schema={tool_yaml["output_schema"]},
    risk="{risk}",
    annotations={{"native": True}},
)


def handle(call: ToolCall) -> ToolResult:
    text = call.args.get("text", "")
    if not isinstance(text, str):
        return ToolResult(
            content=[{{"type": "text", "text": "text 必須是字串"}}],
            is_error=True,
            meta={{"status": "invalid_args"}},
        )
    return ToolResult(
        content=[{{"type": "text", "text": text.upper()}}],
        is_error=False,
        meta={{"status": "ok"}},
    )
''',
        encoding="utf-8",
    )


class ToolforgeTests(unittest.TestCase):
    def test_parse_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir)
            _write_sample_tool(tool_dir, name="demo")
            manifest, violations = parse_native_manifest(tool_dir, strict=True)
            self.assertEqual(manifest.name, "demo")
            self.assertEqual(violations, [])

    def test_rejects_high_risk_allow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_dir = Path(temp_dir)
            _write_sample_tool(tool_dir, name="demo", risk="high")
            tool_yaml = yaml.safe_load((tool_dir / "tool.yaml").read_text(encoding="utf-8"))
            tool_yaml["default_permission"] = "allow"
            (tool_dir / "tool.yaml").write_text(
                yaml.safe_dump(tool_yaml, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaises(Exception):
                parse_native_manifest(tool_dir, strict=True)

    def test_toolforge_init_and_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                tool_dir = core.toolforge_init("demo", base_dir=Path(temp_dir))
                self.assertTrue((tool_dir / "tool.yaml").exists())
                install_entry = core.toolforge_install(tool_dir)
                self.assertEqual(install_entry["name"], "demo")
                index_path = Path(temp_dir) / "cache" / "toolforge_index.json"
                self.assertTrue(index_path.exists())
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_toolforge_verify_and_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                source = Path(temp_dir) / "source"
                _write_sample_tool(source, name="hello")
                core.toolforge_install(source)
                entries = core.toolforge_verify()
                self.assertEqual(entries[0]["name"], "hello")
                output = self._run_cli(["tools", "call", "native:hello", "--args", json.dumps({"text": "hi"})])
                payload = json.loads(output)
                self.assertEqual(payload.get("status"), "ok")
                self.assertEqual(payload.get("text"), "HI")
            finally:
                os.environ.pop("AMON_HOME", None)

    def _run_cli(self, args: list[str]) -> str:
        original_argv = sys.argv
        sys.argv = ["amon", *args]
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                cli.main()
        finally:
            sys.argv = original_argv
        return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
