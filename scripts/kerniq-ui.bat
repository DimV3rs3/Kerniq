@echo off
cd /d "%~dp0.."
if exist ".kerniq\install.json" (
  findstr /C:"\"created_venv\": true" ".kerniq\install.json" >nul
  if not errorlevel 1 if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m Kerniq plugins ui
    goto :eof
  )
  if not errorlevel 1 if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" -m Kerniq plugins ui
    goto :eof
  )
)
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" pythonw -m Kerniq plugins ui
) else (
  start "" python -m Kerniq plugins ui
)