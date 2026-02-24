#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python}"

echo "[codex-cloud] compileall smoke check"
"${PYTHON_BIN}" -m compileall src tests

echo "[codex-cloud] unit tests"
"${PYTHON_BIN}" -m unittest discover -s tests -p 'test_*.py'

echo "[codex-cloud] pip check"
"${PYTHON_BIN}" -m pip check
