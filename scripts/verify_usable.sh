#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export AMON_DATA_DIR="${AMON_DATA_DIR:-$(mktemp -d)}"
UI_PORT="${AMON_UI_PORT:-8765}"
export UI_PORT
UI_LOG="${AMON_DATA_DIR}/ui.log"

cleanup() {
  if [[ -n "${UI_PID:-}" ]] && kill -0 "${UI_PID}" 2>/dev/null; then
    kill "${UI_PID}" 2>/dev/null || true
    wait "${UI_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "[1/6] install package"
python -m pip install -e .

echo "[2/6] run unit tests"
python -m unittest discover -s tests -p 'test_*.py' -v

echo "[3/6] check CLI entry"
amon --help >/dev/null

echo "[4/6] boot UI and probe HTTP endpoint"
amon --data-dir "${AMON_DATA_DIR}" ui --port "${UI_PORT}" >"${UI_LOG}" 2>&1 &
UI_PID=$!
python - <<'PY'
import time
import urllib.request
import urllib.error
import os

port = int(os.environ["UI_PORT"])
url = f"http://127.0.0.1:{port}/"
for _ in range(20):
    try:
        with urllib.request.urlopen(url, timeout=1) as resp:  # noqa: S310
            if resp.status == 200:
                break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(0.25)
else:
    raise SystemExit(f"UI probe failed: {url}")
PY

echo "[5/6] create project and run quickstart graph"
PROJECT_CREATE_OUTPUT="$(amon --data-dir "${AMON_DATA_DIR}" project create "Quickstart")"
printf '%s\n' "${PROJECT_CREATE_OUTPUT}"
PROJECT_ID="$(printf '%s\n' "${PROJECT_CREATE_OUTPUT}" | awk -F '：' '/專案 ID/{print $2; exit}' | tr -d '[:space:]')"
if [[ -z "${PROJECT_ID}" ]]; then
  echo "failed to parse project id" >&2
  exit 1
fi
echo "project_id=${PROJECT_ID}"

set +e
amon --data-dir "${AMON_DATA_DIR}" graph run --project "${PROJECT_ID}" --graph "${ROOT_DIR}/examples/quickstart_project/graph.json"
GRAPH_EXIT_CODE=$?
set -e
if [[ ${GRAPH_EXIT_CODE} -ne 0 ]]; then
  echo "graph run failed (likely missing provider/API key), continue to validate docs output" >&2
fi

echo "[6/6] verify docs output exists"
OUTPUT_FILE="${AMON_DATA_DIR}/projects/${PROJECT_ID}/docs/hello.txt"
test -f "${OUTPUT_FILE}" || (echo "missing output: ${OUTPUT_FILE}" && exit 1)
echo "OK"
