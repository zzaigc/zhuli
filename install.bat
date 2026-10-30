@echo off
REM 安装依赖 + 把 Chromium 下载到项目子目录 .zhuli_runtime\browsers（绝不进 C 盘）
setlocal
cd /d %~dp0
set PLAYWRIGHT_BROWSERS_PATH=%~dp0.zhuli_runtime\browsers
if not exist "%~dp0.zhuli_runtime\venv\Scripts\python.exe" python -m venv .zhuli_runtime\venv
call .zhuli_runtime\venv\Scripts\activate.bat
python -m pip install -U pip
pip install -r requirements.txt
playwright install chromium
endlocal
