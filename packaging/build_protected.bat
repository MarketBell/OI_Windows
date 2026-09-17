@echo off
REM ============================================================
REM  OI Pulse Dashboard - HARDENED build (PyArmor + PyInstaller)
REM  Obfuscates app.py, token_manager.py, license_manager.py so the
REM  license check cannot be trivially stripped, then packs everything
REM  into the .exe. Run build.bat FIRST and confirm it works before
REM  using this one.
REM
REM  Needs PyArmor 8.x:  py -m pip install --upgrade pyarmor
REM  (PyArmor may require a free registration for some features; see
REM   https://pyarmor.readthedocs.io )
REM ============================================================
setlocal
cd /d "%~dp0.."

echo.
echo [1/3] Installing / updating build tools...
py -m pip install -r requirements.txt           || goto :err
py -m pip install --upgrade pyinstaller pyarmor  || goto :err

echo.
echo [2/3] Cleaning previous build output...
if exist build     rmdir /s /q build
if exist dist       rmdir /s /q dist
if exist obfdist    rmdir /s /q obfdist

echo.
echo [3/3] Obfuscating + packing with PyArmor (uses the PyInstaller spec)...
REM  --pack takes our spec so the onedir layout, datas and hidden imports
REM  are all preserved; PyArmor obfuscates the named scripts and injects
REM  its runtime, then hands off to PyInstaller.
pyarmor gen --pack packaging\oi_pulse.spec app.py token_manager.py license_manager.py || goto :err

echo.
echo ============================================================
echo  DONE (hardened). App folder: dist\OI Pulse Dashboard\
echo  Test it, then build the installer with packaging\installer.iss.
echo.
echo  NOTE: PyArmor's exact CLI can differ between versions. If the
echo  --pack step errors, see BUILD.md "Option 2b" for the manual
echo  two-step flow (obfuscate, then run PyInstaller on obfdist).
echo ============================================================
goto :eof

:err
echo.
echo *** HARDENED BUILD FAILED - see the error above. ***
echo     If it's the PyArmor step, fall back to build.bat + read BUILD.md.
exit /b 1
