@echo off
REM Zhuli v0.3.0 安装脚本（Windows）。Linux/macOS 请用 scripts/install.sh。
REM 作用：创建虚拟环境、安装依赖、准备 Chromium、最后做自检。
REM Chromium 与浏览器 profile 一律放在项目内的 .zhuli_runtime\ 目录，绝不进 C 盘系统缓存。
REM 复用脚本找到已有 Chromium 时会跳过重新下载。
setlocal
cd /d %~dp0
set PLAYWRIGHT_BROWSERS_PATH=%~dp0.zhuli_runtime\browsers
if not exist "%~dp0.zhuli_runtime\venv\Scripts\python.exe" python -m venv .zhuli_runtime\venv
call .zhuli_runtime\venv\Scripts\activate.bat
python -m pip install -U pip
pip install -r requirements.txt
REM 先尝试复用已有 Chromium，找不到时再下载。
if exist "scripts\reuse_chromium.bat" (
  call scripts\reuse_chromium.bat
  if errorlevel 2 (
    python -m playwright install chromium
  ) else (
    echo 已复用 Chromium，跳过下载。
  )
) else (
  python -m playwright install chromium
)
echo 安装完成，正在自检……
if exist "scripts\doctor.bat" (
  call scripts\doctor.bat
) else (
  set PYTHONPATH=%~dp0src
  python -m zhuli.main --check
)
if not exist "config\settings.yaml" (
  echo 下一步：copy config\settings.yaml.example config\settings.yaml，然后填入你自己的模型配置。
)
echo 下一步：运行 run.bat 启动服务。
endlocal
