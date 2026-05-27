<#
.SYNOPSIS
    Create a minimal dev-stub sidecar so that `cargo tauri dev` can compile.

.DESCRIPTION
    Tauri's Rust build script requires every externalBin file to exist on disk
    before it compiles, even in dev mode.  This script uses PyInstaller to
    produce a tiny stub executable that just prints "PORT=8000" and exits.

    The real backend is built by:  make bundle-backend  (runs PyInstaller on
    the full hermes.spec).  This script only needs to be run once (or after
    cleaning src-tauri/resources/).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Triple  = "x86_64-pc-windows-msvc"
$DestDir = "src-tauri\resources"
$Dest    = "$DestDir\hermes-server-$Triple.exe"

# Already exists — nothing to do.
if (Test-Path $Dest) {
    Write-Host "Dev stub already present: $Dest" -ForegroundColor Green
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

# ── Build the stub ───────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

& $Python -m PyInstaller `
    --onefile `
    --console `
    --name hermes-server `
    --distpath $DestDir `
    --workpath "build\pyinstaller-stub" `
    --noconfirm `
    "packaging\pyinstaller\hermes_stub.py"

if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed." }

# ── Rename to include target triple ─────────────────────────────────────────
$Raw = "$DestDir\hermes-server.exe"
if (Test-Path $Dest) { Remove-Item $Dest -Force }
Move-Item $Raw $Dest

Write-Host "Dev stub created: $Dest" -ForegroundColor Green
Write-Host "(Run 'make bundle-backend' to replace this with the real backend binary.)"
