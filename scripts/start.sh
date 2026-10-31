#!/bin/sh
# Zhuli v0.3.0 启动脚本（Linux/macOS）。Windows 请用 run.bat。
# 如果虚拟环境不存在，先自动运行安装脚本，再启动服务。
set -eu
cd "$(dirname "$0")/.."
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.zhuli_runtime/browsers"
if [ ! -f .zhuli_runtime/venv/bin/activate ]; then
  echo "未找到虚拟环境，先运行安装脚本……"
  scripts/install.sh
fi
. .zhuli_runtime/venv/bin/activate
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
exec python -m zhuli.main
