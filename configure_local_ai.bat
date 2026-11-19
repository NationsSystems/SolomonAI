@echo off
"%~dp0.venv\Scripts\python.exe" "%~dp0configure_local_ai.py"
exit /b %errorlevel%
