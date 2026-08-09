@echo off
setlocal
set "REPO_DIR=%~dp0"
if exist "%REPO_DIR%dist\YidaAI\YidaAI.exe" (
  start "" "%REPO_DIR%dist\YidaAI\YidaAI.exe"
  exit /b 0
)
if exist "%REPO_DIR%.venv\Scripts\pythonw.exe" (
  start "" "%REPO_DIR%.venv\Scripts\pythonw.exe" -m yida_ai
  exit /b 0
)
echo Yida AI is not built and .venv is missing. See README.zh-CN.md.
exit /b 1
