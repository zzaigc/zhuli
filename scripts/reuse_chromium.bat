@echo off
REM Zhuli v0.3.0 复用 Chromium 脚本（Windows）。Linux/macOS 请用 scripts/reuse_chromium.sh。
REM 用途：在重新下载约 197 MB 的 Chromium 之前，先复用项目内或同级目录里已有的 Chromium。
REM 返回值：0 表示已复用（调用方应跳过下载）；2 表示没有找到可复用的 Chromium（调用方应下载）。
REM 本脚本只复制浏览器二进制目录，不改写 .zhuli_runtime\profile、memory.db、配置文件和虚拟环境。
setlocal
cd /d %~dp0..
if not exist ".zhuli_runtime\browsers" mkdir ".zhuli_runtime\browsers"
dir /b ".zhuli_runtime\browsers" 2>nul | findstr /i "chromium" >nul
if not errorlevel 1 (
  echo 项目内已有 Chromium，跳过下载：.zhuli_runtime\browsers
  endlocal & exit /b 0
)
REM 候选来源：命令行参数优先，其次是同级目录。
if not "%~1"=="" (
  if exist "%~1" (
    xcopy /E /Y /I "%~1\chromium-*" ".zhuli_runtime\browsers\" >nul
    echo 复用 Chromium，来源：%~1
    echo 已复制到：.zhuli_runtime\browsers，跳过下载。
    endlocal & exit /b 0
  )
)
if exist "..\.zhuli_runtime\browsers" (
  xcopy /E /Y /I "..\.zhuli_runtime\browsers\chromium-*" ".zhuli_runtime\browsers\" >nul
  echo 复用 Chromium，来源：同级目录的 .zhuli_runtime\browsers
  endlocal & exit /b 0
)
if exist "..\zhuli\.zhuli_runtime\browsers" (
  xcopy /E /Y /I "..\zhuli\.zhuli_runtime\browsers\chromium-*" ".zhuli_runtime\browsers\" >nul
  echo 复用 Chromium，来源：同级 zhuli 目录
  endlocal & exit /b 0
)
echo 没有找到可复用的 Chromium，需要下载。
endlocal & exit /b 2
