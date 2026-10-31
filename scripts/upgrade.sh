#!/bin/sh
# Zhuli v0.3.0 就地升级脚本（Linux/macOS）。Windows 请用 scripts/upgrade.bat。
# 用法：scripts/upgrade.sh <新版本解压目录>
# 新版本目录里必须有 pyproject.toml 和 src/zhuli。
# 只覆盖代码、脚本、文档和版本文件，绝不改动以下数据：
#   .zhuli_runtime/venv、.zhuli_runtime/browsers、.zhuli_runtime/profile、
#   .zhuli_runtime/memory.db、.zhuli_runtime/usage.db、config/settings.yaml、
#   .git、frontend/node_modules、__pycache__。
# 安全说明：本脚本在复制脚本文件时会跳过它自己（scripts/upgrade.sh），
# 避免正在运行的脚本被覆盖导致中断；升级后如提示升级脚本有新版，请手动复制它。
# 升级后不自动安装依赖、不删除虚拟环境；如需新依赖，请运行 scripts/install.sh。
set -eu
if [ $# -lt 1 ] || [ -z "$1" ]; then
  echo "用法：scripts/upgrade.sh <新版本解压目录>"
  echo "示例：scripts/upgrade.sh /tmp/zhuli-v0.3.0"
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$(cd "$1" && pwd)"
if [ ! -f "$ROOT/pyproject.toml" ] || [ ! -d "$ROOT/src/zhuli" ]; then
  echo "错误：当前目录不是 Zhuli 项目（缺少 pyproject.toml 或 src/zhuli）。"
  exit 1
fi
if [ ! -f "$SRC/pyproject.toml" ] || [ ! -d "$SRC/src/zhuli" ]; then
  echo "错误：新版本目录不是 Zhuli 项目（缺少 pyproject.toml 或 src/zhuli）。"
  exit 1
fi
if [ "$ROOT" = "$SRC" ]; then
  echo "错误：新版本目录不能和当前项目是同一个目录。"
  exit 1
fi
echo "当前项目：$ROOT"
echo "新版本来源：$SRC"
echo "以下数据不会被改动：.zhuli_runtime、config/settings.yaml、.git、frontend/node_modules"
# 只复制白名单路径；来源里没有的路径直接跳过，不删除目标里的旧文件。
copy_dir() {
  if [ -d "$SRC/$1" ]; then
    mkdir -p "$ROOT/$1"
    cp -a "$SRC/$1/." "$ROOT/$1/"
    echo "已更新目录：$1"
  fi
}
copy_file() {
  if [ -f "$SRC/$1" ]; then
    mkdir -p "$ROOT/$(dirname "$1")"
    cp -a "$SRC/$1" "$ROOT/$1"
    echo "已更新文件：$1"
  fi
}
copy_dir src
copy_dir docs
copy_file frontend/package.json
copy_file frontend/package-lock.json
copy_file frontend/index.html
copy_file frontend/postcss.config.js
copy_dir frontend/src
copy_file README.md
copy_file LICENSE
copy_file CONTRIBUTING.md
copy_file pyproject.toml
copy_file requirements.txt
copy_file install.bat
copy_file run.bat
# 脚本目录：先复制除升级脚本本身以外的文件。
if [ -d "$SRC/scripts" ]; then
  mkdir -p "$ROOT/scripts"
  for f in "$SRC"/scripts/*; do
    [ -e "$f" ] || continue
    base="$(basename "$f")"
    if [ "$base" = "upgrade.sh" ] || [ "$base" = "upgrade.bat" ]; then
      continue
    fi
    cp -a "$f" "$ROOT/scripts/"
  done
  echo "已更新目录：scripts（升级脚本本身未自动覆盖）"
fi
# 升级脚本本身如有新版，只做提示，不自动覆盖正在运行的文件。
if [ -f "$SRC/scripts/upgrade.sh" ]; then
  if ! cmp -s "$SRC/scripts/upgrade.sh" "$ROOT/scripts/upgrade.sh"; then
    echo "提示：新版本里升级脚本有变化，请手动复制：cp $SRC/scripts/upgrade.sh $ROOT/scripts/upgrade.sh"
  fi
fi
for f in "$SRC"/RELEASE_NOTES*.md; do
  [ -e "$f" ] || continue
  cp -a "$f" "$ROOT/"
  echo "已更新文件：$(basename "$f")"
done
echo "---- 升级后检查 ----"
if [ -f "$ROOT/.zhuli_runtime/venv/bin/python" ]; then
  PYTHONPATH="$ROOT/src" "$ROOT/.zhuli_runtime/venv/bin/python" -m zhuli.main --check || echo "自检未通过，请查看上面的错误（数据未被改动）。"
else
  echo "未找到虚拟环境，跳过 zhuli.main --check；请运行 scripts/install.sh 完成安装。"
fi
echo "就地升级完成。数据未动：.zhuli_runtime、config/settings.yaml 均未被改写。"
echo "下一步：如新版本需要新依赖，请运行 scripts/install.sh；然后运行 scripts/start.sh 启动。"
