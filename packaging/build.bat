@echo off
REM ============================================================
REM  OI Pulse Dashboard - plain build (PyInstaller only)
REM  Use this first to confirm the .exe runs. Add protection later
REM  with build_protected.bat (PyArmor).
REM ============================================================
setlocal
cd /d "%~dp0.."

echo.
echo [1/3] Installing / updating build tools...
py -m pip install --upgrade pip                 >nul 2>&1
py -m pip install -r requirements.txt           || goto :err
py -m pip install --upgrade pyinstaller         || goto :err

echo.
echo [2/3] Cleaning previous build output...
if exist build   rmdir /s /q build
if exist dist     rmdir /s /q dist

echo.
echo [3/3] Building with PyInstaller...
py -m PyInstaller packaging\oi_pulse.spec --noconfirm || goto :err

echo.
echo ============================================================
echo  DONE. App folder: dist\OI Pulse Dashboard\
echo  Test it: run  "dist\OI Pulse Dashboard\OI Pulse Dashboard.exe"
echo  Then build the installer: open packaging\installer.iss in Inno Setup.
echo ============================================================
goto :eof

:err
echo.
echo *** BUILD FAILED - see the error above. ***
exit /b 1
