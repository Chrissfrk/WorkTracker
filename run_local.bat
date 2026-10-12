@echo off
rem Starts Work Tracker locally and opens the browser. Close this window to stop it.
cd /d "%~dp0"
start "" http://localhost:5000
".venv\Scripts\python.exe" app.py
pause
