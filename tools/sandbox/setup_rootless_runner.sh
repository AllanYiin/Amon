#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR=""
HOST="127.0.0.1"
PORT="8088"
IMAGE="amon-sandbox-python:latest"

usage() {
  cat <<'USAGE'
Usage:
  bash tools/sandbox/setup_rootless_runner.sh --project-dir <amon_repo_path> [--host 127.0.0.1] [--port 8088] [--image amon-sandbox-python:latest]

This script installs/updates a user-level systemd service for amon-sandbox-runner.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --image)
      IMAGE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$PROJECT_DIR" ]]; then
  echo "--project-dir is required" >&2
  usage
  exit 1
fi

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl not found; this script requires systemd user services" >&2
  exit 1
fi

mkdir -p "$HOME/.config/systemd/user"
SERVICE_PATH="$HOME/.config/systemd/user/amon-sandbox-runner.service"

cat > "$SERVICE_PATH" <<SERVICE
[Unit]
Description=Amon Sandbox Runner (user)
After=network.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
Environment=AMON_SANDBOX_HOST=$HOST
Environment=AMON_SANDBOX_PORT=$PORT
Environment=AMON_SANDBOX_IMAGE=$IMAGE
ExecStart=$HOME/.local/bin/amon-sandbox-runner
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
SERVICE

systemctl --user daemon-reload
systemctl --user enable --now amon-sandbox-runner

echo "Installed: $SERVICE_PATH"
echo "Service status:"
systemctl --user --no-pager --full status amon-sandbox-runner || true
