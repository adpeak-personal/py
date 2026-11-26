@echo off
rem 블로그 작업기 — 더블클릭으로 띄운다.
rem pythonw 라서 검은 콘솔 창이 안 뜬다. 로그는 프로그램 창 안에 쌓인다.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" gui.py
