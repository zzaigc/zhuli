@echo off
REM Zhuli v0.3.0 就地升级脚本（Windows）。Linux/macOS 请用 scripts/upgrade.sh。
REM 用法：scripts\upgrade.bat <新版本解压目录>
REM 新版本目录里必须有 pyproject.toml 和 src\zhuli。
REM 只覆盖代码、脚本、文档和版本文件，绝不改动以下数据：
REM   .zhuli_runtime\venv、.zhuli_runtime\browsers、.zhuli_runtime\profile、
REM   .zhuli_runtime\memory.db、.zhuli_runtime\usage.db、config\settings.yaml、
REM   .git、frontend\node_modules。
REM 安全说明：本脚本在复制脚本文件时会跳过它自己，避免正在运行的脚本被覆盖；
REM 升级后如提示升级脚本有新版，请手动复制它。
REM 升级后不自动安装依赖、不删除虚拟环境；如需新依赖，请运行 install.bat。
setlocal
if "%~1"=="" (
  echo 用法：scripts\upgrade.bat ^<新版本解压目录^>
  echo 示例：scripts\upgrade.bat C:\Downloads\zhuli-v0.3.0
  endlocal & exit /b 1
)
cd /d %~dp0..
set "ROOT=%CD%"
set "SRC=%~1"
if not exist "%ROOT%\pyproject.toml" (
  echo 错误：当前目录不是 Zhuli 项目（缺少 pyproject.toml）。
  endlocal & exit /b 1
)
if not exist "%ROOT%\src\zhuli" (
  echo 错误：当前目录不是 Zhuli 项目（缺少 src\zhuli）。
  endlocal & exit /b 1
)
if not exist "%SRC%\pyproject.toml" (
  echo 错误：新版本目录不是 Zhuli 项目（缺少 pyproject.toml）。
  endlocal & exit /b 1
)
if not exist "%SRC%\src\zhuli" (
  echo 错误：新版本目录不是 Zhuli 项目（缺少 src\zhuli）。
  endlocal & exit /b 1
)
echo 当前项目：%ROOT%
echo 新版本来源：%SRC%
echo 以下数据不会被改动：.zhuli_runtime、config\settings.yaml、.git、frontend\node_modules
if exist "%SRC%\src" xcopy /E /Y /I "%SRC%\src" "%ROOT%\src" >nul && echo 已更新目录：src
if exist "%SRC%\docs" xcopy /E /Y /I "%SRC%\docs" "%ROOT%\docs" >nul && echo 已更新目录：docs
if exist "%SRC%\frontend\src" xcopy /E /Y /I "%SRC%\frontend\src" "%ROOT%\frontend\src" >nul && echo 已更新目录：frontend\src
if exist "%SRC%\frontend\package.json" copy /Y "%SRC%\frontend\package.json" "%ROOT%\frontend\package.json" >nul && echo 已更新文件：frontend\package.json
if exist "%SRC%\frontend\index.html" copy /Y "%SRC%\frontend\index.html" "%ROOT%\frontend\index.html" >nul && echo 已更新文件：frontend\index.html
if exist "%SRC%\README.md" copy /Y "%SRC%\README.md" "%ROOT%\README.md" >nul && echo 已更新文件：README.md
if exist "%SRC%\LICENSE" copy /Y "%SRC%\LICENSE" "%ROOT%\LICENSE" >nul && echo 已更新文件：LICENSE
if exist "%SRC%\pyproject.toml" copy /Y "%SRC%\pyproject.toml" "%ROOT%\pyproject.toml" >nul && echo 已更新文件：pyproject.toml
if exist "%SRC%\requirements.txt" copy /Y "%SRC%\requirements.txt" "%ROOT%\requirements.txt" >nul && echo 已更新文件：requirements.txt
if exist "%SRC%\install.bat" copy /Y "%SRC%\install.bat" "%ROOT%\install.bat" >nul && echo 已更新文件：install.bat
if exist "%SRC%\run.bat" copy /Y "%SRC%\run.bat" "%ROOT%\run.bat" >nul && echo 已更新文件：run.bat
REM 脚本目录：跳过升级脚本本身，见上方安全说明。
for %%F in ("%SRC%\scripts\*") do (
  if /I not "%%~nxF"=="upgrade.sh" if /I not "%%~nxF"=="upgrade.bat" copy /Y "%%F" "%ROOT%\scripts\" >nul
)
echo 已更新目录：scripts（升级脚本本身未自动覆盖）
for %%F in ("%SRC%\RELEASE_NOTES*.md") do copy /Y "%%F" "%ROOT%\" >nul && echo 已更新文件：%%~nxF
echo ---- 升级后检查 ----
if exist "%ROOT%\.zhuli_runtime\venv\Scripts\python.exe" (
  set PYTHONPATH=%ROOT%\src
  "%ROOT%\.zhuli_runtime\venv\Scripts\python.exe" -m zhuli.main --check
  if errorlevel 1 echo 自检未通过，请查看上面的错误（数据未被改动）。
) else (
  echo 未找到虚拟环境，跳过 zhuli.main --check；请运行 install.bat 完成安装。
)
echo 就地升级完成。数据未动：.zhuli_runtime、config\settings.yaml 均未被改写。
echo 下一步：如新版本需要新依赖，请运行 install.bat；然后运行 run.bat 启动。
endlocal
