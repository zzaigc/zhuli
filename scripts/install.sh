#!/bin/sh
# Zhuli v0.2.0 install (Linux/macOS). Windows users: use install.bat.
# Chromium and the browser profile stay inside .zhuli_runtime/ in this
# project directory; they are never written to the system cache.
set -eu
cd "$(dirname "$0")/.."
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.zhuli_runtime/browsers"
python3 -m venv .zhuli_runtime/venv 2>/dev/null || true
. .zhuli_runtime/venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
python -m playwright install chromium
echo "Installed. Next: cp config/settings.yaml.example config/settings.yaml"
