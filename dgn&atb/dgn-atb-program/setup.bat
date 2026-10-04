@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM  First-time setup on a new PC: create .venv and install packages.
REM  Then copy secrets in (not in git):
REM    atb\.env              (see atb\.env.example)
REM    dgn\daggn-*.json      (Google OAuth client secrets)
REM    dgn\token-*.json      (optional; login pops up if missing)
REM ============================================================

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv || python -m venv .venv || goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail

echo.
echo Done. Run start.bat
pause
exit /b 0

:fail
echo.
echo Setup failed.
pause
exit /b 1
