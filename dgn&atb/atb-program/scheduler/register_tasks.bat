@echo off
setlocal

REM ============================================================
REM  Register AllThat collection jobs in Windows Task Scheduler.
REM  New PC: clone code + create .venv + copy .env + prepare MySQL,
REM  then double-click this file. Re-running overwrites the same tasks.
REM
REM    09:00  K-apt nationwide sync  (quota resets at midnight, but the portal
REM                                  returned HTTP_ERROR for every call at 01:00,
REM                                  so run it in daytime instead)
REM    04:00  Geocode                (new complexes + retry errors)
REM    06:00  Applyhome presale      (latest notices)
REM
REM  Runs only while this PC is on and this user is logged in.
REM  Details: scheduler\run_job.py
REM ============================================================

set "HERE=%~dp0"
for %%I in ("%HERE%..") do set "ROOT=%%~fI"
set "PYW=%ROOT%\.venv\Scripts\pythonw.exe"
set "JOB=%HERE%run_job.py"

if not exist "%PYW%" (
  echo [ERROR] venv not found: %PYW%
  echo         In atb-program run:  python -m venv .venv  then  .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
if not exist "%ROOT%\.env" (
  echo [ERROR] %ROOT%\.env not found. Put API keys and DB settings there first.
  pause
  exit /b 1
)

call :reg "AllThat\KaptSync"    09:00 kapt    || goto :fail
call :reg "AllThat\Geocode"     04:00 geocode || goto :fail
call :reg "AllThat\PresaleSync" 06:00 presale || goto :fail

echo.
echo Done. Check: Task Scheduler app ^> Task Scheduler Library ^> AllThat
echo Logs: %ROOT%\logs
pause
exit /b 0

:reg
schtasks /Create /F /SC DAILY /ST %2 /TN %1 /TR "\"%PYW%\" \"%JOB%\" %3" >nul
if errorlevel 1 (
  echo [FAILED] %~1
  exit /b 1
)
echo [OK] %~1  daily %2
exit /b 0

:fail
echo.
echo Registration failed.
pause
exit /b 1
