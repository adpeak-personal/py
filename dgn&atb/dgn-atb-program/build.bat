@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM  Build dist\dgn-atb\ (exe folder) for a PC without Python.
REM  Copy the whole dist\dgn-atb folder to the laptop and run dgn-atb.exe.
REM
REM  Settings live NEXT TO the exe (not inside it), copied from here:
REM    atb\.env                 DB / API keys
REM    dgn\daggn-*.json         Google OAuth client secrets
REM    dgn\token-*.json         Google login tokens (login pops up if missing)
REM    dgn\last_check_time.txt  sheet checkpoint
REM  Rebuilding keeps existing settings/logs in dist (only the program is replaced).
REM ============================================================

if not exist ".venv\Scripts\python.exe" call setup.bat || goto :fail
".venv\Scripts\python.exe" -m pip install -q pyinstaller || goto :fail

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath build\out --workpath build\work dgn-atb.spec || goto :fail

set "OUT=dist\dgn-atb"
if not exist "%OUT%" mkdir "%OUT%"
REM replace program files only
if exist "%OUT%\_internal" rmdir /s /q "%OUT%\_internal"
robocopy "build\out\dgn-atb" "%OUT%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

if not exist "%OUT%\atb" mkdir "%OUT%\atb"
if not exist "%OUT%\dgn" mkdir "%OUT%\dgn"
copy /y "atb\.env.example" "%OUT%\atb\" >nul
REM settings: copy only if missing so values edited on the laptop are not overwritten
if not exist "%OUT%\atb\.env" if exist "atb\.env" copy "atb\.env" "%OUT%\atb\" >nul
for %%F in (dgn\daggn-*.json dgn\token-*.json dgn\last_check_time.txt) do (
  if not exist "%OUT%\dgn\%%~nxF" copy "%%F" "%OUT%\dgn\" >nul
)

echo.
echo Done: %OUT%\dgn-atb.exe
echo Copy the whole %OUT% folder to the laptop.
pause
exit /b 0

:fail
echo.
echo Build failed.
pause
exit /b 1
