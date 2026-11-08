#!/bin/bash
# Build Callguard.app (macOS). Run from anywhere, with the same Python/venv you use for the app.
set -euo pipefail
cd "$(dirname "$0")"
python -c "import py2app" 2>/dev/null || python -m pip install "py2app==0.28.8"
rm -rf build dist
python setup.py py2app -A >/dev/null
echo "Built $(pwd)/dist/Callguard.app"
echo "Open it:  open \"$(pwd)/dist/Callguard.app\""
