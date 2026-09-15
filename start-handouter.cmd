@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run setup-handouter.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" setup_handouter.py --start
if errorlevel 1 pause
