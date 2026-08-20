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

REM --- Install dependencies ------------------------------------------------
REM The marker alone is not enough: if requirements.txt gains a package, an
REM existing environment would silently never receive it. Verify the imports
REM actually work and reinstall if they do not.
set "NEEDS_INSTALL="
if not exist "venv\.installed" set "NEEDS_INSTALL=1"
if not defined NEEDS_INSTALL (
  "venv\Scripts\python.exe" -c "import fastapi, uvicorn, dotenv, openai, zoneinfo; zoneinfo.ZoneInfo('America/Los_Angeles')" >nul 2>&1
  if errorlevel 1 (
    echo   Dependencies are out of date; updating...
    set "NEEDS_INSTALL=1"
  )
)

if defined NEEDS_INSTALL (
  echo   First run: downloading dependencies ^(about 5 MB, usually under a minute^).
  echo   This happens once. Later launches start immediately.
  echo.
  REM Deliberately NOT --quiet: silence for minutes looks like a hang.
  "venv\Scripts\python.exe" -m pip install --upgrade pip
  "venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo   Dependency installation failed. Check your internet connection.
    pause
    exit /b 1
  )
  echo installed > "venv\.installed"
  echo.
  echo   Done. Gemini and Claude are optional extras; add them any time with:
  echo     venv\Scripts\python.exe -m pip install -r requirements-gemini.txt
  echo     venv\Scripts\python.exe -m pip install -r requirements-anthropic.txt
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
