#!/bin/sh
# Zhuli v0.3.0 控制台构建脚本（Linux/macOS）。
# 为什么需要这个脚本，而不是直接运行 npm run build：
# 前端 vite 配置里 emptyOutDir 为 true，构建会清空
# src/zhuli/console/static/，从而删掉 v0.2.0 的覆盖层文件
# （hacker.css、sidebar.css/js、hive.css/js）。
# 本脚本在构建后从 frontend/console-overlays/（覆盖层源文件）
# 恢复这些文件，并给生成的 index.html 重新加上覆盖层引用。
# Windows 上没有对应的 .bat：请在有 Node 的机器上按同样步骤操作，
# 即先 npm run build，再复制覆盖层文件并修补 index.html。
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
npm run build
cd "$ROOT"
cp frontend/console-overlays/hacker.css frontend/console-overlays/sidebar.css frontend/console-overlays/hive.css frontend/console-overlays/parallel.css frontend/console-overlays/sidebar.js frontend/console-overlays/hive.js frontend/console-overlays/parallel.js src/zhuli/console/static/
# 给生成的 index.html 补上覆盖层引用（如果已经存在则不再重复添加）。
if ! grep -q "hacker.css" src/zhuli/console/static/index.html; then
  python3 - <<'PY'
import pathlib
p = pathlib.Path("src/zhuli/console/static/index.html")
t = p.read_text(encoding="utf-8")
t = t.replace(
    "</head>",
    '    <link rel="stylesheet" href="/static/hacker.css">\n'
    '    <link rel="stylesheet" href="/static/sidebar.css">\n'
    '    <link rel="stylesheet" href="/static/hive.css">\n'
    '    <link rel="stylesheet" href="/static/parallel.css">\n  </head>',
    1,
)
t = t.replace(
    "</body>",
    '    <script src="/static/sidebar.js"></script>\n'
    '    <script src="/static/hive.js"></script>\n'
    '    <script src="/static/parallel.js"></script>\n  </body>',
    1,
)
p.write_text(t, encoding="utf-8")
PY
fi
echo "控制台构建完成，覆盖层已恢复：hacker.css、sidebar.css/js、hive.css/js、parallel.css/js。"
