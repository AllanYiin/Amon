#!/usr/bin/env bash
set -u

MODE="${ANTI_LEGACY_MODE:-fail}"
if [[ "${MODE}" != "warn" && "${MODE}" != "fail" ]]; then
  echo "[anti-legacy-graph] invalid ANTI_LEGACY_MODE=${MODE}, expected warn|fail" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}" || exit 2

echo "[anti-legacy-graph] scanning repository: ${ROOT_DIR}"
echo "[anti-legacy-graph] mode: ${MODE}"

output="$(python - <<'PY'
from pathlib import Path

violations: list[str] = []

core_path = Path('src/amon/core.py')
core_text = core_path.read_text(encoding='utf-8')
start = core_text.find('def run_graph(')
end = core_text.find('\n    def run_taskgraph2(', start)
if start == -1 or end == -1:
    violations.append('src/amon/core.py:run_graph function not found for legacy scan')
else:
    run_graph_body = core_text[start:end]
    forbidden = ('schema_version', 'TaskGraphRuntime', 'loads_task_graph')
    for token in forbidden:
        if token in run_graph_body:
            violations.append(f'src/amon/core.py:run_graph contains forbidden token: {token}')
    required = ('Unsupported graph format', 'Run migrator: amon graph migrate ...')
    for token in required:
        if token not in run_graph_body:
            violations.append(f'src/amon/core.py:run_graph missing required token: {token}')

for path in [Path('src/amon/cli.py'), Path('src/amon/commands/executor.py'), Path('src/amon/hooks/runner.py')]:
    text = path.read_text(encoding='utf-8')
    if 'from amon.graph_runtime import GraphRuntime' in text:
        violations.append(f'{path}: direct GraphRuntime import is forbidden in graph.run entrypoints')

ui_text = Path('src/amon/ui_server.py').read_text(encoding='utf-8')
if 'edge.get("from_node")' in ui_text or 'edge.get("to_node")' in ui_text:
    violations.append('src/amon/ui_server.py: mermaid renderer still has legacy/v2 edge key fallback')

if violations:
    print('\n'.join(violations))
PY
)"

if [[ -n "${output}" ]]; then
  echo "${output}"
  if [[ "${MODE}" == "fail" ]]; then
    echo "[anti-legacy-graph] FAIL: legacy graph-run paths detected."
    exit 1
  fi
  echo "[anti-legacy-graph] WARN: references detected."
  exit 0
fi

echo "[anti-legacy-graph] PASS: no legacy graph-run paths detected."
exit 0
