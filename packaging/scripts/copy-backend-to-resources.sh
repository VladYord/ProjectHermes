#!/usr/bin/env bash
# copy-backend-to-resources.sh — Copy the built backend sidecar bundle into Tauri resources.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."

SRC_DIR="backend/dist"
SRC_BUNDLE="${SRC_DIR}/hermes-server"
DEST_DIR="src-tauri/resources"
DEST_BUNDLE="${DEST_DIR}/hermes-server"
DEST_EXE="${DEST_BUNDLE}/hermes-server"

echo "=== Copy backend binary to Tauri resources ==="
echo "Source : ${SRC_BUNDLE}"
echo "Dest   : ${DEST_BUNDLE}"

if [ ! -d "$SRC_BUNDLE" ]; then
    echo "ERROR: source bundle not found: ${SRC_BUNDLE}" >&2
    echo "Run 'make bundle-backend' first." >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
rm -rf "$DEST_BUNDLE"
cp -R "$SRC_BUNDLE" "$DEST_BUNDLE"

if [ ! -f "$DEST_EXE" ] && [ ! -f "${DEST_EXE}.exe" ]; then
    echo "ERROR: copied bundle missing executable: ${DEST_EXE}[.exe]" >&2
    exit 1
fi

if [ -f "$DEST_EXE" ]; then
    chmod +x "$DEST_EXE"
fi

SIZE_MB=$(du -sm "$DEST_BUNDLE" | cut -f1)
echo "Copied bundle to resources."
echo "Bundle size: ${SIZE_MB} MB"
echo "Ready for 'cargo tauri build'"