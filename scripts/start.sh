#!/bin/sh
# Zhuli v0.2.0 start (Linux/macOS). Windows users: use run.bat.
set -eu
cd "$(dirname "$0")/.."
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.zhuli_runtime/browsers"
if [ -f .zhuli_runtime/venv/bin/activate ]; then
  . .zhuli_runtime/venv/bin/activate
fi
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
exec python -m zhuli.main
