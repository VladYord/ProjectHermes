#!/usr/bin/env bash
# create-dev-stub.sh — Create a minimal dev-stub sidecar for cargo tauri dev.
#
# Tauri's Rust build script requires every externalBin file to exist on disk
# before compilation, even in dev mode.  This script PyInstaller-bundles a
# tiny stub that just prints "PORT=8000" and exits.
#
# The real backend is built by:  make bundle-backend

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

PLATFORM="$(uname -s)"
ARCH="$(uname -m)"
DEST_DIR="src-tauri/resources"

if [ "$PLATFORM" = "Darwin" ]; then
    TRIPLE="$( [ "$ARCH" = "arm64" ] && echo "aarch64-apple-darwin" || echo "x86_64-apple-darwin" )"
else
    TRIPLE="x86_64-unknown-linux-gnu"
fi

DEST="${DEST_DIR}/hermes-server-${TRIPLE}"

# Already exists — nothing to do.
if [ -f "$DEST" ]; then
    echo "Dev stub already present: $DEST"
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

"$PYTHON" -m PyInstaller \
    --onefile \
    --console \
    --name hermes-server \
    --distpath "$DEST_DIR" \
    --workpath build/pyinstaller-stub \
    --noconfirm \
    packaging/pyinstaller/hermes_stub.py

mv "${DEST_DIR}/hermes-server" "$DEST"
chmod +x "$DEST"

echo "Dev stub created: $DEST"
echo "(Run 'make bundle-backend' to replace this with the real backend binary.)"
