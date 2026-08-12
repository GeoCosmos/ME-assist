@echo off
setlocal
title ME Assistant - close this window to stop the server

REM Always run from the folder this file lives in, not wherever it was launched.
cd /d "%~dp0"

echo.
echo   ME ASSISTANT
echo   ------------
echo.

REM --- Locate Python ------------------------------------------------------
REM "py -3" is preferred: a bare "python" on Windows often opens the Store.
set "PYCMD="
py -3 --version >nul 2>&1 && set "PYCMD=py -3"
if not defined PYCMD (
  python --version >nul 2>&1 && set "PYCMD=python"
)
if not defined PYCMD (
  echo   Python 3 was not found on this computer.
  echo.
  echo   Install it from https://www.python.org/downloads/
  echo   and make sure "Add python.exe to PATH" is checked during setup.
  echo.
  pause
  exit /b 1
)

REM --- Create the virtual environment on first run ------------------------
if not exist "venv\Scripts\python.exe" (
  echo   First run: creating the Python environment. This takes a minute...
  %PYCMD% -m venv venv
  if errorlevel 1 (
    echo.
    echo   Could not create the virtual environment.
    pause
    exit /b 1
  )
)

REM --- Install dependencies once, then skip on later launches -------------
REM Delete venv\.installed to force a reinstall after changing requirements.
if not exist "venv\.installed" (
  echo   Installing dependencies...
  "venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
  "venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
  if errorlevel 1 (
    echo.
    echo   Dependency installation failed. Check your internet connection.
    pause
    exit /b 1
  )
  echo installed > "venv\.installed"
)

REM --- Make sure there is somewhere to put API keys -----------------------
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo   No API keys are set yet.
  echo   Opening the .env file - paste at least your Gemini key, save, and close it.
  echo   (You can also add keys later from the API KEYS button in the app.)
  echo.
  notepad ".env"
)

REM --- Run ----------------------------------------------------------------
"venv\Scripts\python.exe" launch.py

echo.
echo   The server has stopped.
pause
