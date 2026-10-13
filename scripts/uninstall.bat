@echo off
REM Uninstall package (+ optional project wipe)
cd /d "%~dp0.."
set WIPE=
if /I "%~1"=="--wipe-project" set WIPE=--wipe-project
if /I "%~1"=="wipe" set WIPE=--wipe-project
echo Uninstalling Kerniq...
python -m Kerniq uninstall -y %WIPE%
if errorlevel 1 (
  python -m pip uninstall Kerniq -y
)
echo Done.
pause
