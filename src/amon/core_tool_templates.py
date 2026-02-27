"""Template rendering helpers used by AmonCore toolforge flows."""

from __future__ import annotations


def render_tool_template(tool_name: str, spec: str) -> str:
    if "大寫" in spec or "轉大寫" in spec:
        body = "result = text.upper()"
    else:
        body = "result = text"
    return f'''"""Amon tool: {tool_name}."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def _log_error(message: str) -> None:
    log_dir = Path(os.getenv("AMON_TOOL_LOG_DIR", ".")).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "{tool_name}.log"
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    log_path.write_text(f"[{{timestamp}}] ERROR {{message}}\\n", encoding="utf-8")


def _load_payload() -> dict:
    raw = sys.stdin.read().strip() or "{{}}"
    return json.loads(raw)


def main() -> None:
    try:
        payload = _load_payload()
        text = payload.get("text", "")
        if not isinstance(text, str):
            raise ValueError("text 必須是字串")
        {body}
        output = {{"result": result}}
        sys.stdout.write(json.dumps(output, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        _log_error(str(exc))
        sys.stdout.write(json.dumps({{"error": "執行失敗", "detail": str(exc)}}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
'''


def render_tool_readme(tool_name: str, spec: str) -> str:
    return f"""# {tool_name}

需求：{spec}

## 使用方式

```bash
echo '{{"text": "hello"}}' | python tool.py
```

輸出：

```json
{{"result": "HELLO"}}
```
"""


def render_tool_test(tool_name: str) -> str:
    return f'''"""Tool test for {tool_name}."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    tool_path = Path(__file__).resolve().parents[1] / "tool.py"
    payload = {{"text": "hello"}}
    result = subprocess.run(
        [sys.executable, str(tool_path)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr)
    output = json.loads(result.stdout or "{{}}")
    if output.get("result") != "HELLO":
        raise SystemExit("輸出不符合預期")


if __name__ == "__main__":
    main()
'''


def render_native_tool_template(tool_name: str) -> str:
    return f'''"""Amon native tool: {tool_name}."""

from __future__ import annotations

from amon.tooling.types import ToolCall, ToolResult, ToolSpec

TOOL_SPEC = ToolSpec(
    name="native:{tool_name}",
    description="{tool_name} native tool",
    input_schema={{
        "type": "object",
        "properties": {{"text": {{"type": "string"}}}},
        "required": ["text"],
    }},
    output_schema={{
        "type": "object",
        "properties": {{"result": {{"type": "string"}}}},
        "required": ["result"],
    }},
    risk="low",
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
    result = text.upper()
    return ToolResult(
        content=[{{"type": "text", "text": result}}],
        is_error=False,
        meta={{"status": "ok"}},
    )
'''


def render_native_tool_readme(tool_name: str) -> str:
    return f"""# {tool_name}

這是 toolforge native tool 範例。

## 使用方式

透過 `amon tools call native:{tool_name} --args '{{\"text\":\"hello\"}}'` 呼叫。
"""


def render_native_tool_test(tool_name: str) -> str:
    return f'''"""Toolforge native tool test for {tool_name}."""

from __future__ import annotations

import unittest


class NativeToolPlaceholderTests(unittest.TestCase):
    def test_placeholder(self) -> None:
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
'''
