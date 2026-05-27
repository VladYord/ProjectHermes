<#
.SYNOPSIS
    Build the Hermes backend server using PyInstaller (Windows).

.DESCRIPTION
    Produces a single-file executable suitable for bundling with the Tauri app.
    The output is placed in src-tauri/resources/ and renamed to include the
    Rust target triple so Tauri can auto-bundle it.

.PARAMETER OutputDir
    Destination directory for the built binary (default: src-tauri\resources).

.PARAMETER VenvPython
    Path to the Python executable to use (default: .venv\Scripts\python.exe).

.EXAMPLE
    .\packaging\scripts\build-backend.ps1
    .\packaging\scripts\build-backend.ps1 -OutputDir "C:\custom\path"
#>
param(
    [string]$OutputDir  = "src-tauri\resources",
    [string]$VenvPython = ".venv\Scripts\python.exe"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Resolve paths ────────────────────────────────────────────────────────────
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Push-Location $ProjectRoot

try {
    # ── Python interpreter ───────────────────────────────────────────────────
    if (-not (Test-Path $VenvPython)) {
        # Fall back to system python if venv not present (CI / fresh clone)
        $VenvPython = "python"
    }
    $PythonExe = $VenvPython
    $resolved = Get-Command $VenvPython -ErrorAction SilentlyContinue
    if ($resolved) { $PythonExe = $resolved.Source }

    Write-Host "`n=== Hermes backend build (Windows) ===" -ForegroundColor Cyan
    Write-Host "Python  : $PythonExe"
    Write-Host "Output  : $OutputDir"

    # ── Ensure PyInstaller is available ─────────────────────────────────────
    & $PythonExe -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller not found. Run: $PythonExe -m pip install pyinstaller"
    }

    # ── Copy Tesseract from system install (if not already in packaging/) ───
    $TessWin  = "packaging\tesseract\win"
    $TessData = "packaging\tesseract\tessdata"
    $SystemTess = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    $SystemData = "C:\Program Files\Tesseract-OCR\tessdata\eng.traineddata"

    if (-not (Test-Path "$TessWin\tesseract.exe") -and (Test-Path $SystemTess)) {
        Write-Host "Copying Tesseract binary from system install..."
        New-Item -ItemType Directory -Force -Path $TessWin | Out-Null
        Copy-Item $SystemTess "$TessWin\tesseract.exe"
    }
    if (-not (Test-Path "$TessData\eng.traineddata") -and (Test-Path $SystemData)) {
        Write-Host "Copying Tesseract tessdata (eng)..."
        New-Item -ItemType Directory -Force -Path $TessData | Out-Null
        Copy-Item $SystemData "$TessData\eng.traineddata"
    }

    # ── Run PyInstaller ──────────────────────────────────────────────────────
    Write-Host "`nRunning PyInstaller..." -ForegroundColor Cyan
    & $PythonExe -m PyInstaller `
        packaging\pyinstaller\hermes.spec `
        --distpath $OutputDir `
        --workpath build\pyinstaller `
        --noconfirm

    if ($LASTEXITCODE -ne 0) {
        Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
    }

    # ── Rename to include Rust target triple ─────────────────────────────────
    $Triple  = "x86_64-pc-windows-msvc"
    $SrcExe  = Join-Path $OutputDir "hermes-server.exe"
    $DestExe = Join-Path $OutputDir "hermes-server-$Triple.exe"

    if (Test-Path $DestExe) { Remove-Item $DestExe -Force }
    Move-Item $SrcExe $DestExe
    Write-Host "`nBuild complete: $DestExe" -ForegroundColor Green

    $SizeMB = [math]::Round((Get-Item $DestExe).Length / 1MB, 1)
    Write-Host "Binary size  : ${SizeMB} MB"

} finally {
    Pop-Location
}
