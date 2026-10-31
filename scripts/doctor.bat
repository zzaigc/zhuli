@echo off
REM Zhuli v0.3.0 自检脚本（Windows）。Linux/macOS 请用 scripts/doctor.sh。
REM 只做检查，不安装、不改写任何数据、不调用模型。
setlocal
cd /d %~dp0..
echo 项目根：%CD%
echo ---- 虚拟环境 ----
if exist ".zhuli_runtime\venv\Scripts\python.exe" (
  echo 已找到：.zhuli_runtime\venv\Scripts\python.exe
) else (
  echo 未找到虚拟环境：.zhuli_runtime\venv
  echo 请先运行 install.bat 完成安装。
)
echo ---- 配置文件 ----
if exist "config\settings.yaml" (
  echo 已找到：config\settings.yaml
) else (
  echo 未找到 config\settings.yaml
  echo 下一步：copy config\settings.yaml.example config\settings.yaml，然后填入你自己的模型配置。
)
echo ---- Chromium ----
echo 目录：.zhuli_runtime\browsers
dir /b ".zhuli_runtime\browsers" 2>nul | findstr /i "chromium" >nul
if errorlevel 1 (
  echo 未找到 Chromium（安装时会下载到项目内，不会写系统缓存）。
) else (
  dir /b ".zhuli_runtime\browsers"
)
echo ---- 运行时目录 ----
if exist ".zhuli_runtime" (
  echo 已找到：.zhuli_runtime
) else (
  echo 未找到 .zhuli_runtime（安装时会创建）。
)
echo ---- 程序自检 ----
if exist ".zhuli_runtime\venv\Scripts\python.exe" (
  set PYTHONPATH=%CD%\src
  ".zhuli_runtime\venv\Scripts\python.exe" -m zhuli.main --check
) else (
  echo 跳过 zhuli.main --check（没有虚拟环境）。
)
echo 自检完成。
endlocal
