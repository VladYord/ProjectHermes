#!/usr/bin/env bash
# copy-backend-to-resources.sh — Copy the built backend sidecar into Tauri resources.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

PLATFORM="$(uname -s)"
ARCH="$(uname -m)"
TARGET_TRIPLE="${TARGET_TRIPLE:-}"

if [ -z "$TARGET_TRIPLE" ]; then
    if [ "$PLATFORM" = "Darwin" ]; then
        TARGET_TRIPLE="$( [ "$ARCH" = "arm64" ] && echo "aarch64-apple-darwin" || echo "x86_64-apple-darwin" )"
    else
        TARGET_TRIPLE="x86_64-unknown-linux-gnu"
    fi
fi

SRC_DIR="backend/dist"
SRC="${SRC_DIR}/hermes-server-${TARGET_TRIPLE}"
DEST_DIR="src-tauri/resources"
DEST="${DEST_DIR}/hermes-server-${TARGET_TRIPLE}"

echo "=== Copy backend binary to Tauri resources ==="
echo "Source : ${SRC}"
echo "Dest   : ${DEST}"

if [ ! -f "$SRC" ]; then
    echo "ERROR: source binary not found: ${SRC}" >&2
    echo "Run 'make bundle-backend' first." >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
rm -f "$DEST"
cp "$SRC" "$DEST"
chmod +x "$DEST"

SIZE_MB=$(du -m "$DEST" | cut -f1)
echo "Copied to resources."
echo "Binary size: ${SIZE_MB} MB"
echo "Ready for 'cargo tauri build'"