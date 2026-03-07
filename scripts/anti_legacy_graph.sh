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

ROOT = Path('.')
violations: list[str] = []

deleted_paths = [
    'src/amon/graph_runtime.py',
    'src/amon/taskgraph2',
]
for item in deleted_paths:
    if Path(item).exists():
        violations.append(f'{item}: deleted legacy path still exists')

core_path = Path('src/amon/core.py')
core_text = core_path.read_text(encoding='utf-8')
start = core_text.find('def run_graph(')
if start == -1:
    violations.append('src/amon/core.py: run_graph function not found')
else:
    run_graph_body = core_text[start:]
    required = ('Unsupported graph format', 'Run migrator: amon graph migrate ...')
    for token in required:
        if token not in run_graph_body:
            violations.append(f'src/amon/core.py:run_graph missing required token: {token}')

for path in ROOT.rglob('*'):
    if not path.is_file():
        continue
    rel = path.as_posix()
    if '/.git/' in rel or rel.startswith('.git/'):
        continue
    rel_parts = path.parts
    if 'taskgraph2' in rel_parts:
        violations.append(f'{rel}: forbidden legacy path name')
        continue
    if path.name == 'graph_runtime.py':
        violations.append(f'{rel}: forbidden legacy path name')

scan_globs = ('src/**/*.py', 'tests/**/*.py', 'docs/**/*.md', 'scripts/**/*.sh', '.github/workflows/*.yml')
for pattern in scan_globs:
    for path in ROOT.glob(pattern):
        if not path.is_file():
            continue
        if path.as_posix() == 'scripts/anti_legacy_graph.sh':
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        if 'amon.taskgraph2' in text or 'amon.graph_runtime' in text:
            violations.append(f'{path.as_posix()}: forbidden legacy import reference')

for doc_path in ROOT.glob('docs/**/*.md'):
    text = doc_path.read_text(encoding='utf-8', errors='ignore')
    for deleted in deleted_paths:
        if deleted in text:
            violations.append(f'{doc_path.as_posix()}: references deleted path {deleted}')

if violations:
    print('\n'.join(sorted(set(violations))))
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
