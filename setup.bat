@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"

if exist "%VENV_PY%" goto verify_packages

echo SolomonAI: creating isolated Python 3.11 environment...
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.11 for Windows, then rerun setup.bat.
  exit /b 1
)
py -3.11 -m venv "%ROOT%.venv"
if errorlevel 1 (
  echo Python 3.11 virtual environment creation failed.
  exit /b 1
)

:verify_packages
"%VENV_PY%" -c "import pymysql, flask, waitress, torch, transformers, accelerate, huggingface_hub" >nul 2>nul
if not errorlevel 1 goto configure_database

echo SolomonAI: installing application and local AI packages into .venv...
"%VENV_PY%" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 goto failed_dependencies

echo Installing reference NVIDIA CUDA PyTorch (for the verified Windows configuration)...
"%VENV_PY%" -m pip install "torch==2.12.0" --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 goto failed_dependencies
"%VENV_PY%" -m pip install -r "%ROOT%requirements-ai.txt"
if errorlevel 1 goto failed_dependencies
"%VENV_PY%" -m pip check
if errorlevel 1 goto failed_dependencies

:configure_database
"%VENV_PY%" "%ROOT%setup.py"
exit /b %errorlevel%

:failed_dependencies
echo Dependency installation incomplete. Inspect the error and rerun setup.bat.
echo On non-NVIDIA systems, a different PyTorch build may be necessary.
exit /b 1
