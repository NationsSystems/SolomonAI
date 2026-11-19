@echo off
setlocal
"%~dp0.venv\Scripts\python.exe" "%~dp0start.py"
exit /b %errorlevel%
