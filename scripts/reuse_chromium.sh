#!/bin/sh
# Zhuli v0.3.0 复用 Chromium 脚本（Linux/macOS）。Windows 请用 scripts/reuse_chromium.bat。
# 用途：在重新下载约 197 MB 的 Chromium 之前，先复用项目内或同级目录里已有的 Chromium。
# 返回值：0 表示已复用（调用方应跳过下载）；2 表示没有找到可复用的 Chromium（调用方应下载）。
# 本脚本只复制浏览器二进制目录，不改写 .zhuli_runtime/profile、memory.db、配置文件和虚拟环境。
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/.zhuli_runtime/browsers"
mkdir -p "$DEST"
# 项目内已经有 Chromium，直接跳过下载。
if ls "$DEST"/chromium-* >/dev/null 2>&1; then
  echo "项目内已有 Chromium，跳过下载：$DEST"
  exit 0
fi
# 候选来源：命令行参数优先，其次是同级目录和常见系统缓存。
CANDIDATES=""
if [ $# -ge 1 ] && [ -n "$1" ]; then
  CANDIDATES="$1"
fi
if [ -n "${REUSE_CHROMIUM_DIR:-}" ]; then
  CANDIDATES="$CANDIDATES $REUSE_CHROMIUM_DIR"
fi
CANDIDATES="$CANDIDATES $ROOT/../.zhuli_runtime/browsers $ROOT/../zhuli/.zhuli_runtime/browsers $HOME/.cache/ms-playwright"
for SRC in $CANDIDATES; do
  if [ -d "$SRC" ] && ls "$SRC"/chromium-* >/dev/null 2>&1; then
    echo "复用 Chromium，来源：$SRC"
    cp -a "$SRC"/chromium-* "$DEST"/
    echo "已复制到：$DEST，跳过下载。"
    exit 0
  fi
done
echo "没有找到可复用的 Chromium，需要下载。"
exit 2
