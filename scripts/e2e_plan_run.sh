#!/usr/bin/env bash
set -euo pipefail

TASK="${1:-}"
if [[ -z "${TASK}" ]]; then
  echo "Usage: $0 '<task>'" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${2:-${REPO_ROOT}/.tmp/e2e_plan_run}"
mkdir -p "${OUT_DIR}"

export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}"

run_amon() {
  python - "$@" <<'PY'
import sys
from amon.cli import main

sys.argv = ["amon", *sys.argv[1:]]
main()
PY
}

for STEP in step1 step2 step3 step4 step5; do
  run_amon plan "${STEP}" --task "${TASK}" --out-dir "${OUT_DIR}"
done

run_amon run step6 --task "${TASK}" --project e2e --out-dir "${OUT_DIR}" --graph "${OUT_DIR}/graph.v3.json"

required=(
  "${OUT_DIR}/graph.v3.json"
  "${OUT_DIR}/graph.mmd"
  "${OUT_DIR}/run.state.json"
  "${OUT_DIR}/events.jsonl"
)

for artifact in "${required[@]}"; do
  if [[ ! -f "${artifact}" ]]; then
    echo "Missing artifact: ${artifact}" >&2
    exit 1
  fi
done

echo "Artifacts generated in ${OUT_DIR}"
