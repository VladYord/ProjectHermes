# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Hermes backend server.
#
# Usage (from project root):
#   pyinstaller packaging/pyinstaller/hermes.spec \
#       --distpath src-tauri/resources \
#       --workpath build/pyinstaller \
#       --noconfirm
#
# The produced binary is renamed to hermes-server-{triple} by the build scripts.

import sys
from pathlib import Path

# SPECPATH is set by PyInstaller to the directory containing this spec file.
# Project root is two levels up: packaging/pyinstaller/ → packaging/ → root
PROJECT_ROOT = Path(SPECPATH).parent.parent

block_cipher = None

IS_WINDOWS = sys.platform == 'win32'
IS_MAC     = sys.platform == 'darwin'
IS_LINUX   = sys.platform.startswith('linux')

# ---------------------------------------------------------------------------
# Tesseract OCR — optional; gracefully absent if not found on this machine.
# In CI, the binaries are pre-downloaded to packaging/tesseract/ before build.
# ---------------------------------------------------------------------------
TESSERACT_WIN   = PROJECT_ROOT / 'packaging/tesseract/win/tesseract.exe'
TESSERACT_MAC   = PROJECT_ROOT / 'packaging/tesseract/mac/tesseract'
TESSERACT_LINUX = PROJECT_ROOT / 'packaging/tesseract/linux/tesseract'
TESSDATA_DIR    = PROJECT_ROOT / 'packaging/tesseract/tessdata'

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

# ---------------------------------------------------------------------------
# collect_all() — must be called explicitly; it is NOT a valid Analysis() kwarg.
# Collects every submodule, data file, and binary from the named package so
# that dynamic string-based imports (e.g. chromadb.telemetry.product.posthog)
# are found at runtime inside the frozen bundle.
# ---------------------------------------------------------------------------
from PyInstaller.utils.hooks import collect_all

extra_hiddenimports = []

for _pkg in [
    'chromadb',
    'onnxruntime',
    'langchain',
    'langchain_core',
    'langchain_community',
    'langchain_ollama',
    'langchain_openai',
    'langchain_google_genai',
    'langchain_litellm',
    'litellm',
    'tiktoken',
    'posthog',          # chromadb telemetry back-end
    'pydantic_core',    # pydantic binary extension (critical dependency)
]:
    try:
        _d, _b, _h = collect_all(_pkg)
        datas    += _d
        binaries += _b
        extra_hiddenimports += _h
    except Exception:
        pass  # package not installed — skip silently

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(PROJECT_ROOT / 'hermes' / '__main__.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # ChromaDB — dynamic loader targets (importlib.import_module strings)
        'chromadb',
        'chromadb_rust_bindings',
        'chromadb.telemetry',
        'chromadb.telemetry.product',
        'chromadb.telemetry.product.posthog',
        'chromadb.db.mixins',
        'chromadb.segment',
        'chromadb.segment.impl',
        'chromadb.segment.impl.metadata',
        'chromadb.segment.impl.metadata.sqlite',
        'chromadb.segment.impl.vector',
        'chromadb.segment.impl.vector.local_persistent_hnsw',
        'chromadb.migrations',
        # onnxruntime
        'onnxruntime',
        'onnxruntime.capi',
        'onnxruntime.capi._pybind_state',
        # LangChain providers
        'langchain_ollama',
        'langchain_openai',
        'langchain_google_genai',
        'langchain_community',
        # Tokenization plugins used by LiteLLM/OpenAI model helpers
        'tiktoken',
        'tiktoken_ext',
        'tiktoken_ext.openai_public',
        # Document parsers
        'fitz',         # PyMuPDF
        'docx',
        'PIL',
        'pytesseract',
        # FastAPI / Uvicorn entry points (all loaded by string at runtime)
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
        # Cryptography back-end
        'cryptography',
        'cryptography.hazmat.backends.openssl',
        'cryptography.hazmat.primitives.ciphers.aead',
        # Async SQLite (sessions)
        'aiosqlite',
        # MCP
        'mcp',
        # Windows bundled sqlite3
        '_sqlite3',
        # Email / multipart (FastAPI dependency)
        'email.mime.multipart',
        'email.mime.text',
    ] + extra_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'notebook',
        'IPython',
        'scipy',
        'pandas',
        'pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='hermes-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,    # Hidden window; port file fallback handles stdout capture loss
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='hermes-server',
)
