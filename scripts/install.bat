@echo off
REM One-click Kerniq install (Windows, minimal windows)
cd /d "%~dp0.."
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found on PATH. Install Python 3.11+ and retry.
  pause
  exit /b 1
)
echo Installing Kerniq editable with [dev,mcp]...
python -m pip install -e ".[dev,mcp]"
if errorlevel 1 (
  echo pip install failed.
  pause
  exit /b 1
)
echo.
python -m Kerniq --version
echo.
echo Done. Try: kerniq plugins ui
echo If kerniq is not found, add Python Scripts to PATH or use: python -m Kerniq ...
pause
