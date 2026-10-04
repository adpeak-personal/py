@echo off
REM Remove all AllThat scheduled jobs. Code and data are not touched.

for %%T in ("AllThat\KaptSync" "AllThat\Geocode" "AllThat\PresaleSync") do (
  schtasks /Delete /F /TN %%T >nul 2>&1 && echo [removed] %%~T || echo [not found] %%~T
)
pause
