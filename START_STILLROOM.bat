@echo off
cd /d "%~dp0"
setlocal
where py >nul 2>nul
if %ERRORLEVEL%==0 (set "PYTHON=py -3") else (set "PYTHON=python")
if not exist ".venv\Scripts\python.exe" (
 echo Setting up Stillroom. An internet connection is needed for first installation.
 %PYTHON% -m venv .venv
 if errorlevel 1 (echo Python 3.10+ is required. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -c "import PySide6" >nul 2>nul
if errorlevel 1 (
 ".venv\Scripts\python.exe" -m pip install -r requirements.txt
 if errorlevel 1 (echo PySide6 installation failed. Check internet access. & pause & exit /b 1)
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
