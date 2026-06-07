<#
.SYNOPSIS
    Create a minimal dev-stub sidecar so that `cargo tauri dev` / `make build-app` can compile.

.DESCRIPTION
    Tauri's Rust build script requires every resource file to exist on disk before
    it compiles.  This script uses PyInstaller's onedir mode to produce a tiny stub
    executable bundle (hermes-server/) that just prints "PORT=8000" and exits.

    The real backend is built by:  make bundle-backend  (runs PyInstaller on
    the full hermes.spec).  This script only needs to be run once (or after
    cleaning src-tauri/resources/).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$DestDir    = "src-tauri\resources"
$DestBundle = "$DestDir\hermes-server"

# Already exists — nothing to do.
if (Test-Path $DestBundle) {
    Write-Host "Dev stub already present: $DestBundle" -ForegroundColor Green
    exit 0
}

Write-Host "Creating dev stub for cargo tauri dev..." -ForegroundColor Cyan

# ── Choose Python interpreter ────────────────────────────────────────────────
$Python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

# ── Ensure PyInstaller is available ─────────────────────────────────────────
& $Python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller not found. Run: $Python -m pip install pyinstaller"
}

# ── Build the stub as onedir ─────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

# Clean any leftover from a prior run
if (Test-Path $DestBundle) { Remove-Item $DestBundle -Recurse -Force }

& $Python -m PyInstaller `
    --onedir `
    --console `
    --name hermes-server `
    --distpath $DestDir `
    --workpath "build\pyinstaller-stub" `
    --noconfirm `
    "packaging\pyinstaller\hermes_stub.py"

if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed." }

Write-Host "Dev stub created: $DestBundle" -ForegroundColor Green
Write-Host "(Run 'make bundle-backend' to replace this with the real backend bundle.)"