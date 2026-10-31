#!/bin/sh
# Zhuli v0.3.0 自检脚本（Linux/macOS）。Windows 请用 scripts/doctor.bat。
# 只做检查，不安装、不改写任何数据、不调用模型。
# 检查项：项目根、虚拟环境、配置文件、Chromium 目录、运行时目录。
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "项目根：$ROOT"
echo "---- 虚拟环境 ----"
if [ -f .zhuli_runtime/venv/bin/python ]; then
  echo "已找到：.zhuli_runtime/venv/bin/python"
  VENV_PY=.zhuli_runtime/venv/bin/python
else
  echo "未找到虚拟环境：.zhuli_runtime/venv"
  echo "请先运行 scripts/install.sh 完成安装。"
  VENV_PY=""
fi
echo "---- 配置文件 ----"
if [ -f config/settings.yaml ]; then
  echo "已找到：config/settings.yaml"
else
  echo "未找到 config/settings.yaml"
  echo "下一步：cp config/settings.yaml.example config/settings.yaml，然后填入你自己的模型配置。"
fi
echo "---- Chromium ----"
echo "目录：.zhuli_runtime/browsers"
if ls .zhuli_runtime/browsers/chromium-* >/dev/null 2>&1; then
  ls -d .zhuli_runtime/browsers/chromium-*
else
  echo "未找到 Chromium（安装时会下载到项目内，不会写系统缓存）。"
fi
echo "---- 运行时目录 ----"
ls -d .zhuli_runtime 2>/dev/null || echo "未找到 .zhuli_runtime（安装时会创建）。"
echo "---- 程序自检 ----"
if [ -n "$VENV_PY" ]; then
  PYTHONPATH="$ROOT/src" "$VENV_PY" -m zhuli.main --check
else
  echo "跳过 zhuli.main --check（没有虚拟环境）。"
fi
echo "自检完成。"
