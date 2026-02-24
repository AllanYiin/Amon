#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PYTHON_BIN="${PYTHON_BIN:-python}"
PIP_BIN=("${PYTHON_BIN}" -m pip)
INSTALL_EXTRAS="${AMON_INSTALL_EXTRAS:-}"

editable_target='.'
if [[ -n "${INSTALL_EXTRAS}" ]]; then
  editable_target=".[${INSTALL_EXTRAS}]"
fi

echo "[codex-cloud] 嘗試自動相依安裝：pip install -e ${editable_target}"
if "${PIP_BIN[@]}" install -e "${editable_target}"; then
  echo "[codex-cloud] 自動安裝成功"
  exit 0
fi

echo "[codex-cloud] 自動安裝失敗，改用明確 setup script 流程"
"${PIP_BIN[@]}" install --upgrade pip setuptools wheel
if [[ -f requirements.txt ]]; then
  "${PIP_BIN[@]}" install -r requirements.txt
fi
"${PIP_BIN[@]}" install -e "${editable_target}"

echo "[codex-cloud] 明確 setup script 流程完成"
