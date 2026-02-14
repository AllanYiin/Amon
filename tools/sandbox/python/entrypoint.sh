#!/usr/bin/env sh
set -eu

TIMEOUT_S="${1:-10}"
CODE_FILE="/tmp/code.py"

cat > "$CODE_FILE"

python - <<'PY' "$TIMEOUT_S" "$CODE_FILE"
import signal
import subprocess
import sys


timeout_s = int(sys.argv[1])
code_file = sys.argv[2]

proc = subprocess.Popen(
    [sys.executable, "-u", code_file],
    cwd="/work",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)


def _kill(*_args):
    try:
        proc.kill()
    except OSError:
        pass

signal.signal(signal.SIGTERM, _kill)

try:
    stdout, stderr = proc.communicate(timeout=timeout_s)
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    raise SystemExit(proc.returncode)
except subprocess.TimeoutExpired:
    _kill()
    stdout, stderr = proc.communicate()
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    sys.stderr.write("\n[timeout] code execution exceeded limit\n")
    raise SystemExit(124)
PY
