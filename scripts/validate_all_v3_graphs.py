from __future__ import annotations

import json
from pathlib import Path

from amon.taskgraph3.migrate import validate_v3_graph_json

SCAN_ROOTS = (Path("examples"), Path("fixtures"), Path("tests/fixtures"))


def main() -> int:
    graph_paths: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        graph_paths.extend(sorted(path for path in root.rglob("*.json") if _looks_like_graph_file(path)))

    failures: list[str] = []
    validated = 0
    for path in graph_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"{path}: JSON decode error: {exc}")
            continue
        if not isinstance(payload, dict) or payload.get("version") != "taskgraph.v3":
            failures.append(f"{path}: expected taskgraph.v3 payload")
            continue
        try:
            validate_v3_graph_json(payload)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{path}: {exc}")
            continue
        validated += 1

    if failures:
        print("[validate_all_v3_graphs] FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print(f"[validate_all_v3_graphs] OK (validated={validated})")
    return 0


def _looks_like_graph_file(path: Path) -> bool:
    lowered = path.name.lower()
    return "graph" in lowered or "taskgraph" in lowered or path.parent.name == "graphs"


if __name__ == "__main__":
    raise SystemExit(main())
