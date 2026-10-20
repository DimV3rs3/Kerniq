@echo off
cd /d "%~dp0.."
set "PYW="
if exist ".kerniq\install.json" (
  findstr /C:"\"created_venv\": true" ".kerniq\install.json" >nul
  if not errorlevel 1 if exist ".venv\Scripts\pythonw.exe" set "PYW=%CD%\.venv\Scripts\pythonw.exe"
)
if not defined PYW (
  where pythonw >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%P in ('where pythonw') do if not defined PYW set "PYW=%%P"
  )
)
if not defined PYW if exist ".venv\Scripts\pythonw.exe" set "PYW=%CD%\.venv\Scripts\pythonw.exe"
if not defined PYW set "PYW=pythonw"
start "" "%PYW%" -m Kerniq plugins ui
exit /b 0
