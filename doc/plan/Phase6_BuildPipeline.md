# Phase 6 — PyInstaller & Tauri Build Pipeline

**Status:** � Complete  
**Depends on:** [Phase5_TauriIntegration.md](Phase5_TauriIntegration.md) 🟢  
**Next phase:** [Phase7_CICD.md](Phase7_CICD.md)

---

## Goal

Produce a single self-contained installer on each target platform:
- `hermes_0.x.x_x64-setup.exe` — Windows NSIS installer
- `hermes_0.x.x_x64.dmg` — macOS disk image
- `hermes_0.x.x_amd64.AppImage` — Linux portable binary
- `hermes_0.x.x_amd64.deb` — Linux Debian package

No end-user needs Python, Node.js, or any other dependency. Everything is bundled.

---

## 🛑 Manual Steps (do before running build scripts)

### 🛠 MANUAL — Install Tesseract OCR on your dev machine (Windows)

The build scripts pick up the Tesseract binary from a known path. On Windows:
1. Download the installer from the **UB-Mannheim** build (official Windows binaries):
   https://github.com/UB-Mannheim/tesseract/wiki → download the latest `.exe`
2. Run the installer → choose install path `C:\Program Files\Tesseract-OCR`
3. During install: check **Additional language data → English** (eng.traineddata)
4. Verify: open a new terminal → `tesseract --version`

The build script `build-backend.ps1` expects:
- Binary at: `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Tessdata at: `C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata`

If you installed to a different path, update the path in `packaging/scripts/build-backend.ps1`.

### 🛠 MANUAL — Install PyInstaller
```powershell
pip install pyinstaller
```
Verify: `pyinstaller --version` prints `6.x.x`

---

## Bundle Contents

```
Tauri app bundle
├── WebView (OS system WebView — WKWebView/WebView2/WebKitGTK)
├── Svelte UI (static HTML/CSS/JS in app bundle)
└── resources/
    └── hermes-server-{target}     ← PyInstaller one-file executable
        ├── Python 3.12 runtime (embedded)
        ├── FastAPI + Uvicorn
        ├── LangChain + all providers
        ├── ChromaDB 1.5.9 + ONNX Runtime
        ├── All document parsers (PyMuPDF, python-docx, etc.)
        ├── Tesseract OCR binary + tessdata (eng)
        └── All other Python dependencies
```

---

## Steps

### 6.1 — Install PyInstaller

```powershell
pip install pyinstaller
```

### 6.2 — Create `packaging/pyinstaller/hermes.spec`

Key PyInstaller directives:

```python
# packaging/pyinstaller/hermes.spec
import sys
from pathlib import Path

block_cipher = None

# Detect platform for Tesseract binary inclusion
IS_WINDOWS = sys.platform == 'win32'
IS_MAC     = sys.platform == 'darwin'
IS_LINUX   = sys.platform.startswith('linux')

# Tesseract binary paths (populated by CI — see Phase 7)
TESSERACT_WIN  = Path('packaging/tesseract/win/tesseract.exe')
TESSERACT_MAC  = Path('packaging/tesseract/mac/tesseract')
TESSERACT_LINUX = Path('packaging/tesseract/linux/tesseract')
TESSDATA_DIR   = Path('packaging/tesseract/tessdata')

binaries = []
if IS_WINDOWS and TESSERACT_WIN.exists():
    binaries += [(str(TESSERACT_WIN), 'tesseract')]
elif IS_MAC and TESSERACT_MAC.exists():
    binaries += [(str(TESSERACT_MAC), 'tesseract')]
elif IS_LINUX and TESSERACT_LINUX.exists():
    binaries += [(str(TESSERACT_LINUX), 'tesseract')]

datas = []
if TESSDATA_DIR.exists():
    datas += [(str(TESSDATA_DIR), 'tessdata')]

a = Analysis(
    ['hermes/__main__.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # ChromaDB
        'chromadb',
        'chromadb.db.mixins',
        'chromadb.segment',
        'chromadb.segment.impl',
        'chromadb.segment.impl.metadata',
        'chromadb.segment.impl.vector',
        'chromadb.segment.impl.vector.local_persistent_hnsw',
        'onnxruntime',
        'onnxruntime.capi',
        # LangChain providers
        'langchain_ollama',
        'langchain_openai',
        'langchain_google_genai',
        'langchain_community',
        # Document parsers
        'fitz',           # PyMuPDF
        'docx',
        'PIL',
        'pytesseract',
        # FastAPI / Uvicorn
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # Cryptography
        'cryptography',
        'cryptography.hazmat.backends.openssl',
        # aiosqlite
        'aiosqlite',
        # MCP
        'mcp',
    ],
    collect_all=[
        'chromadb',
        'onnxruntime',
        'langchain',
        'langchain_core',
        'langchain_community',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'notebook',
        'IPython',
        'scipy',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='hermes-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,    # Must be True — Tauri reads stdout for PORT=XXXX
    icon=None,
)
```

**Output location:** configure `distpath` to `src-tauri/resources/` so Tauri bundles it automatically.

Add to spec or pass via CLI:
```
pyinstaller packaging/pyinstaller/hermes.spec \
  --distpath src-tauri/resources \
  --workpath build/pyinstaller
```

### 6.3 — Platform Tesseract binary acquisition (local dev)

**Windows (PowerShell):**
```powershell
# Download Tesseract installer from UB-Mannheim
# https://github.com/UB-Mannheim/tesseract/wiki
# Run installer, copy binary and tessdata to packaging/tesseract/win/
```

**macOS:**
```bash
brew install tesseract
cp $(which tesseract) packaging/tesseract/mac/
cp -r /usr/local/share/tessdata packaging/tesseract/tessdata/
```

**Linux:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-eng
cp $(which tesseract) packaging/tesseract/linux/
cp -r /usr/share/tesseract-ocr/*/tessdata packaging/tesseract/tessdata/
```

> **Note:** `packaging/tesseract/` is git-ignored. CI downloads binaries in Phase 7.

### 6.4 — Create `packaging/scripts/build-backend.ps1` (Windows)

```powershell
param(
    [string]$OutputDir = "src-tauri\resources"
)

Write-Host "Building hermes-server with PyInstaller..."
python -m PyInstaller `
    packaging\pyinstaller\hermes.spec `
    --distpath $OutputDir `
    --workpath build\pyinstaller `
    --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed"
    exit 1
}

# Rename to include Tauri target triple
$triple = "x86_64-pc-windows-msvc"
Rename-Item "$OutputDir\hermes-server.exe" "$OutputDir\hermes-server-$triple.exe"
Write-Host "Done: $OutputDir\hermes-server-$triple.exe"
```

### 6.5 — Create `packaging/scripts/build-backend.sh` (Unix)

```bash
#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-src-tauri/resources}"
PLATFORM=$(uname -s)

echo "Building hermes-server with PyInstaller..."
python -m PyInstaller \
    packaging/pyinstaller/hermes.spec \
    --distpath "$OUTPUT_DIR" \
    --workpath build/pyinstaller \
    --noconfirm

if [ "$PLATFORM" = "Darwin" ]; then
    TRIPLE="aarch64-apple-darwin"   # or x86_64-apple-darwin
    [ "$(uname -m)" = "x86_64" ] && TRIPLE="x86_64-apple-darwin"
else
    TRIPLE="x86_64-unknown-linux-gnu"
fi

mv "$OUTPUT_DIR/hermes-server" "$OUTPUT_DIR/hermes-server-$TRIPLE"
chmod +x "$OUTPUT_DIR/hermes-server-$TRIPLE"
echo "Done: $OUTPUT_DIR/hermes-server-$TRIPLE"
```

### 6.6 — Update `Makefile`

```makefile
## Build hermes-server binary (platform-appropriate)
bundle-backend:
ifeq ($(OS),Windows_NT)
	powershell -File packaging/scripts/build-backend.ps1
else
	bash packaging/scripts/build-backend.sh
endif

## Full production bundle: backend binary + Tauri installer
bundle-app: bundle-backend build-ui
	cargo tauri build --manifest-path src-tauri/Cargo.toml
```

### 6.7 — Tauri bundle configuration in `src-tauri/tauri.conf.json`

```json
{
  "bundle": {
    "active": true,
    "targets": "all",
    "identifier": "dev.hermes.app",
    "publisher": "Hermes Project",
    "externalBin": ["resources/hermes-server"],
    "icon": ["icons/32x32.png", "icons/128x128.png", "icons/icon.icns", "icons/icon.ico"],
    "windows": {
      "nsis": {
        "displayLanguageSelector": false,
        "installMode": "currentUser"
      }
    },
    "macOS": {
      "entitlements": null,
      "exceptionDomain": "",
      "signingIdentity": null
    },
    "linux": {
      "deb": {
        "depends": []
      }
    }
  }
}
```

---

## Files Created

| File | Purpose |
|---|---|
| `packaging/pyinstaller/hermes.spec` | Full PyInstaller build specification |
| `packaging/scripts/build-backend.ps1` | Windows build script |
| `packaging/scripts/build-backend.sh` | Unix build script |

## Files Modified

| File | Change |
|---|---|
| `Makefile` | Implement `bundle-backend` and `bundle-app` targets |
| `src-tauri/tauri.conf.json` | Bundle configuration (targets, identifier, externalBin, NSIS/DMG/deb settings) |

---

## Known PyInstaller Pain Points

| Issue | Mitigation |
|---|---|
| ChromaDB ONNX Runtime missing | Use `--collect-all chromadb` + `--collect-all onnxruntime` |
| `sqlite3.dll` missing on Windows | Add `hiddenimports=['_sqlite3']` |
| LangChain dynamic imports | Add all `langchain_*` provider packages to `collect_all` |
| `fitz` (PyMuPDF) library path | May need `--add-binary` for platform libmupdf |
| Large output size (~400-600 MB) | Expected; UPX compression reduces ~20% |
| Tesseract not found at runtime | Set `TESSDATA_PREFIX` env var to `sys._MEIPASS/tessdata` in `hermes/__main__.py` when packaged |

Add to `hermes/__main__.py` when packaged:
```python
import sys, os
if getattr(sys, 'frozen', False):
    os.environ['TESSDATA_PREFIX'] = os.path.join(sys._MEIPASS, 'tessdata')
    os.environ['HERMES_PACKAGED'] = '1'
```

---

## Verification Checklist

- [ ] `make bundle-backend` completes without errors
- [ ] `src-tauri/resources/hermes-server-{triple}` binary exists
- [ ] Running `hermes-server-{triple} --port 0` prints `PORT=XXXX` to stdout
- [ ] Running the binary and curling `/api/health` returns `{"status": "ok"}`
- [ ] Ingest a PDF via the binary, confirm ChromaDB created in temp dir
- [ ] OCR test: ingest a PNG → text extracted (Tesseract working)
- [ ] `make bundle-app` produces installer in `src-tauri/target/release/bundle/`
- [ ] Run installer on a clean VM (no Python installed) — app launches, works end-to-end

---

## Completion Notes

> Fill in after phase is completed:
> - Date completed:
> - Final binary size (MB):
> - Build time (minutes):
> - Issues encountered:
> - Deviations from plan:
