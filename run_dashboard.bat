@echo off
title OI Pulse Dashboard
cd /d "%~dp0"
echo Installing/checking required Python packages...
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Check Python and internet connection.
  pause
  exit /b 1
)
echo.
echo Starting OI Pulse at http://127.0.0.1:5069
py app.py
pause
