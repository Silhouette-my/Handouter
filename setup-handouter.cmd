@echo off
cd /d "%~dp0"
py -3.11 setup_handouter.py
if errorlevel 1 echo Setup failed. Check the error above. Python 3.11 must be installed.
pause
