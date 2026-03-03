#!/usr/bin/env bash
set -u

MODE="${ANTI_LEGACY_MODE:-warn}"
if [[ "${MODE}" != "warn" && "${MODE}" != "fail" ]]; then
  echo "[anti-legacy-graph] invalid ANTI_LEGACY_MODE=${MODE}, expected warn|fail" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}" || exit 2

declare -i total_hits=0

scan_block() {
  local title="$1"
  local pattern="$2"
  echo ""
  echo "== ${title} =="
  local output
  output="$(rg -n --no-heading -S --glob '!*.pyc' --glob '!.git/**' "${pattern}" . || true)"
  if [[ -n "${output}" ]]; then
    printf '%s\n' "${output}"
    local count
    count=$(printf '%s\n' "${output}" | wc -l | tr -d '[:space:]')
    echo "[found] ${count} matches"
    total_hits+=count
  else
    echo "[clean] no matches"
  fi
}

echo "[anti-legacy-graph] scanning repository: ${ROOT_DIR}"
echo "[anti-legacy-graph] mode: ${MODE}"

scan_block \
  "Legacy graph runtime references (graph_runtime / GraphRuntime)" \
  "(amon\\.graph_runtime|from\\s+\\.?[a-zA-Z0-9_.]*graph_runtime\\s+import|\\bGraphRuntime\\b)"

scan_block \
  "TaskGraph2 runtime references (taskgraph2 runtime entrypoints)" \
  "(amon\\.taskgraph2|from\\s+\\.?[a-zA-Z0-9_.]*taskgraph2\\s+import|\\bTaskGraphRuntime\\b|\\brun_taskgraph2\\b|\\bloads_task_graph\\b|\\bdumps_task_graph\\b|schema_version\"\\s*:\\s*\"2\\.0\")"

echo ""
echo "[anti-legacy-graph] total matches: ${total_hits}"

if (( total_hits > 0 )); then
  if [[ "${MODE}" == "fail" ]]; then
    echo "[anti-legacy-graph] FAIL: legacy/taskgraph2 references detected."
    exit 1
  fi
  echo "[anti-legacy-graph] WARN: references detected (Stage 0 expected)."
  exit 0
fi

echo "[anti-legacy-graph] PASS: no references detected."
exit 0
