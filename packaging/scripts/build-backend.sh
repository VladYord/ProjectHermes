#!/usr/bin/env bash
# build-backend.sh — Build the Hermes backend server using PyInstaller (macOS / Linux).
#
# Usage:
#   bash packaging/scripts/build-backend.sh [OUTPUT_DIR]
#
# OUTPUT_DIR defaults to src-tauri/resources.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

OUTPUT_DIR="${1:-src-tauri/resources}"
PLATFORM="$(uname -s)"
ARCH="$(uname -m)"
TARGET_TRIPLE="${TARGET_TRIPLE:-}"

if [ -z "${TARGET_TRIPLE}" ]; then
    if [ "${PLATFORM}" = "Darwin" ]; then
        TARGET_TRIPLE="$( [ "${ARCH}" = "arm64" ] && echo "aarch64-apple-darwin" || echo "x86_64-apple-darwin" )"
    else
        TARGET_TRIPLE="x86_64-unknown-linux-gnu"
    fi
fi

echo ""
echo "=== Hermes backend build (${PLATFORM}/${ARCH}) ==="
echo "Output : ${OUTPUT_DIR}"
echo "Target : ${TARGET_TRIPLE}"

# ── Python interpreter ────────────────────────────────────────────────────────
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi
echo "Python : $($PYTHON --version)"

# ── Ensure PyInstaller is installed ──────────────────────────────────────────
if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "ERROR: PyInstaller not found. Run: $PYTHON -m pip install pyinstaller" >&2
    exit 1
fi

# ── Copy Tesseract from system install if not already in packaging/ ───────────
TESS_SRC_MAC="$(which tesseract 2>/dev/null || true)"
TESS_SRC_LINUX="$(which tesseract 2>/dev/null || true)"

if [ "$PLATFORM" = "Darwin" ]; then
    TESS_DIR="packaging/tesseract/mac"
    TESS_BIN="$TESS_DIR/tesseract"
    if [ ! -f "$TESS_BIN" ] && [ -n "$TESS_SRC_MAC" ]; then
        echo "Copying Tesseract binary from $TESS_SRC_MAC ..."
        mkdir -p "$TESS_DIR"
        cp "$TESS_SRC_MAC" "$TESS_BIN"
    fi
else
    TESS_DIR="packaging/tesseract/linux"
    TESS_BIN="$TESS_DIR/tesseract"
    if [ ! -f "$TESS_BIN" ] && [ -n "$TESS_SRC_LINUX" ]; then
        echo "Copying Tesseract binary from $TESS_SRC_LINUX ..."
        mkdir -p "$TESS_DIR"
        cp "$TESS_SRC_LINUX" "$TESS_BIN"
    fi
fi

# ── Copy tessdata (eng) if not already present ────────────────────────────────
TESS_DATA_DEST="packaging/tesseract/tessdata"
if [ ! -f "${TESS_DATA_DEST}/eng.traineddata" ]; then
    for SEARCH_PATH in \
        /usr/local/share/tessdata \
        /usr/share/tessdata \
        /usr/share/tesseract-ocr/5/tessdata \
        /usr/share/tesseract-ocr/4/tessdata \
        /usr/share/tesseract-ocr/tessdata \
        /opt/homebrew/share/tessdata; do
        if [ -f "${SEARCH_PATH}/eng.traineddata" ]; then
            echo "Copying tessdata from ${SEARCH_PATH} ..."
            mkdir -p "$TESS_DATA_DEST"
            cp "${SEARCH_PATH}/eng.traineddata" "$TESS_DATA_DEST/"
            break
        fi
    done
    if [ ! -f "${TESS_DATA_DEST}/eng.traineddata" ]; then
        echo "ERROR: could not find eng.traineddata in any known tessdata location"
        exit 1
    fi
fi

# ── Run PyInstaller ───────────────────────────────────────────────────────────
echo ""
echo "Running PyInstaller..."
"$PYTHON" -m PyInstaller \
    packaging/pyinstaller/hermes.spec \
    --distpath "$OUTPUT_DIR" \
    --workpath build/pyinstaller \
    --noconfirm

# ── Rename to include Rust target triple ──────────────────────────────────────
TRIPLE="${TARGET_TRIPLE}"

SRC="${OUTPUT_DIR}/hermes-server"
DEST="${OUTPUT_DIR}/hermes-server-${TRIPLE}"

if [ -f "$DEST" ]; then rm -f "$DEST"; fi
mv "$SRC" "$DEST"
chmod +x "$DEST"

SIZE_MB=$(du -m "$DEST" | cut -f1)
echo ""
echo "Build complete : $DEST"
echo "Binary size    : ${SIZE_MB} MB"
