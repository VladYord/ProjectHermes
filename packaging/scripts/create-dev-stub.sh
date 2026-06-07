#!/usr/bin/env bash
# create-dev-stub.sh — Create a minimal dev-stub sidecar for cargo tauri dev.
#
# Tauri's Rust build script requires every resource file to exist on disk
# before compilation.  This script uses PyInstaller's onedir mode to produce
# a tiny stub bundle (hermes-server/) that just prints "PORT=8000" and exits.
#
# The real backend is built by:  make bundle-backend

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

DEST_DIR="src-tauri/resources"
DEST_BUNDLE="${DEST_DIR}/hermes-server"

# Already exists — nothing to do.
if [ -d "$DEST_BUNDLE" ]; then
    echo "Dev stub already present: $DEST_BUNDLE"
    exit 0
fi

echo "Creating dev stub for cargo tauri dev..."

# Choose Python
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

# Ensure PyInstaller
if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "ERROR: PyInstaller not found. Run: $PYTHON -m pip install pyinstaller" >&2
    exit 1
fi

mkdir -p "$DEST_DIR"

# Clean any leftover from a prior run
if [ -e "$DEST_BUNDLE" ]; then
    rm -rf "$DEST_BUNDLE"
fi

"$PYTHON" -m PyInstaller \
    --onedir \
    --console \
    --name hermes-server \
    --distpath "$DEST_DIR" \
    --workpath build/pyinstaller-stub \
    --noconfirm \
    packaging/pyinstaller/hermes_stub.py

chmod +x "${DEST_BUNDLE}/hermes-server"

echo "Dev stub created: $DEST_BUNDLE"
echo "(Run 'make bundle-backend' to replace this with the real backend bundle.)"
