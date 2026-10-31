@echo off
REM Zhuli v0.3.0 启动脚本（Windows）。Linux/macOS 请用 scripts/start.sh。
REM 如果虚拟环境不存在，先自动运行安装脚本，再启动服务。
REM Chromium 与用户 profile 均在项目 .zhuli_runtime\ 子目录。
setlocal
cd /d %~dp0
set PLAYWRIGHT_BROWSERS_PATH=%~dp0.zhuli_runtime\browsers
if not exist "%~dp0.zhuli_runtime\venv\Scripts\activate.bat" (
  echo 未找到虚拟环境，先运行安装脚本……
  call install.bat
)
call .zhuli_runtime\venv\Scripts\activate.bat
set PYTHONPATH=%~dp0src;%PYTHONPATH%
python -m zhuli.main
endlocal
