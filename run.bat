@echo off
REM 启动 ZHULI 本地服务（控制台页面 + WebSocket）。Chromium 与用户 profile 均在项目 .zhuli_runtime\ 子目录。
setlocal
cd /d %~dp0
set PLAYWRIGHT_BROWSERS_PATH=%~dp0.zhuli_runtime\browsers
if exist "%~dp0.zhuli_runtime\venv\Scripts\activate.bat" call .zhuli_runtime\venv\Scripts\activate.bat
set PYTHONPATH=%~dp0src;%PYTHONPATH%
python -m zhuli.main
endlocal
