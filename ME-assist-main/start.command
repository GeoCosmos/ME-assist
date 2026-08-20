#!/bin/bash
# macOS double-click launcher. Mirror of start.bat.
# If double-clicking does nothing, run once in Terminal:
#   chmod +x start.command

set -u
cd "$(dirname "$0")" || exit 1

echo
echo "  ME ASSISTANT"
echo "  ------------"
echo

# --- Locate Python -------------------------------------------------------
PYCMD=""
if command -v python3 >/dev/null 2>&1; then
  PYCMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYCMD="python"
fi

if [ -z "$PYCMD" ]; then
  echo "  Python 3 was not found."
  echo "  Install it from https://www.python.org/downloads/ and try again."
  echo
  read -r -p "  Press Return to close." _
  exit 1
fi

# --- Create the virtual environment on first run -------------------------
if [ ! -x "venv/bin/python" ]; then
  echo "  First run: creating the Python environment. This takes a minute..."
  "$PYCMD" -m venv venv || {
    echo "  Could not create the virtual environment."
    read -r -p "  Press Return to close." _
    exit 1
  }
fi

# --- Install dependencies ------------------------------------------------
# The marker alone is not enough: if requirements.txt gains a package, an
# existing environment would silently never receive it. Verify the imports
# actually work and reinstall if they do not.
NEEDS_INSTALL=0
[ ! -f "venv/.installed" ] && NEEDS_INSTALL=1
if [ "$NEEDS_INSTALL" = "0" ]; then
  ./venv/bin/python -c "import fastapi, uvicorn, dotenv, openai, zoneinfo; zoneinfo.ZoneInfo('America/Los_Angeles')" 2>/dev/null || {
    echo "  Dependencies are out of date; updating..."
    NEEDS_INSTALL=1
  }
fi

if [ "$NEEDS_INSTALL" = "1" ]; then
  echo "  First run: downloading dependencies (about 5 MB, usually under a minute)."
  echo "  This happens once. Later launches start immediately."
  echo
  # Deliberately NOT --quiet: with no output this looks frozen, and a slow
  # network turns that into "it's broken".
  ./venv/bin/python -m pip install --upgrade pip
  ./venv/bin/python -m pip install -r requirements.txt || {
    echo "  Dependency installation failed. Check your internet connection."
    read -r -p "  Press Return to close." _
    exit 1
  }
  echo installed > "venv/.installed"
  echo
  echo "  Done. Gemini and Claude are optional extras; add them any time with:"
  echo "    ./venv/bin/python -m pip install -r requirements-gemini.txt"
  echo "    ./venv/bin/python -m pip install -r requirements-anthropic.txt"
fi

# --- Make sure there is somewhere to put API keys ------------------------
if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo
  echo "  No API keys are set yet."
  echo "  Opening the .env file - paste at least your Gemini key and save."
  echo "  (You can also add keys later from the API KEYS button in the app.)"
  echo
  open -e ".env"
  read -r -p "  Press Return once you have saved the file." _
fi

# --- Run ------------------------------------------------------------------
./venv/bin/python launch.py

echo
echo "  The server has stopped."
read -r -p "  Press Return to close." _
