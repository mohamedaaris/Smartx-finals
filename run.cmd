@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel% equ 0 (
  python app.py
) else (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py
)
pause
