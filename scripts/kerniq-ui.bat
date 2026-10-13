@echo off
REM Launch Kerniq Web UI without a persistent console (Windows)
cd /d "%~dp0.."
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" pythonw -m Kerniq plugins ui
) else (
  start "" python -m Kerniq plugins ui
)
