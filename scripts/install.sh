#!/bin/sh
# Zhuli v0.3.0 安装脚本（Linux/macOS）。Windows 请用 install.bat。
# 作用：创建虚拟环境、安装依赖、准备 Chromium、最后做自检。
# Chromium 和浏览器 profile 一律放在项目内的 .zhuli_runtime/ 目录，
# 绝不写系统缓存；复用脚本找到已有 Chromium 时会跳过重新下载。
set -eu
cd "$(dirname "$0")/.."
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.zhuli_runtime/browsers"
python3 -m venv .zhuli_runtime/venv 2>/dev/null || true
. .zhuli_runtime/venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
# 先尝试复用已有 Chromium，找不到时再下载。
if [ -x scripts/reuse_chromium.sh ]; then
  if scripts/reuse_chromium.sh; then
    echo "已复用 Chromium，跳过下载。"
  else
    python -m playwright install chromium
  fi
else
  python -m playwright install chromium
fi
echo "安装完成，正在自检……"
if [ -x scripts/doctor.sh ]; then
  scripts/doctor.sh || true
else
  PYTHONPATH="$PWD/src" python -m zhuli.main --check || true
fi
if [ ! -f config/settings.yaml ]; then
  echo "下一步：cp config/settings.yaml.example config/settings.yaml，然后填入你自己的模型配置。"
fi
echo "下一步：运行 scripts/start.sh 启动服务。"
