<#
.SYNOPSIS
    Build the Hermes backend server using PyInstaller (Windows).

.DESCRIPTION
    Produces an onedir bundle suitable for bundling with the Tauri app.
    The output is placed in backend/dist/ under a target-triple folder.
    A separate copy script moves the bundle into src-tauri/resources/.

.PARAMETER OutputDir
    Destination directory for the built binary (default: backend\dist).

.PARAMETER VenvPython
    Path to the Python executable to use (default: .venv\Scripts\python.exe).

.EXAMPLE
    .\packaging\scripts\build-backend.ps1
    .\packaging\scripts\build-backend.ps1 -OutputDir "C:\custom\path"
#>
param(
    [string]$OutputDir  = "backend\dist",
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

    # ── PyInstaller already produces backend/dist/hermes-server/ ───────────
    $SrcBundle = Join-Path $OutputDir "hermes-server"

    if (-not (Test-Path $SrcBundle)) {
        Write-Error "Expected PyInstaller output directory not found: $SrcBundle"
    }

    $Bytes = (Get-ChildItem $SrcBundle -Recurse -File | Measure-Object -Property Length -Sum).Sum
    $SizeMB = [math]::Round($Bytes / 1MB, 1)
    Write-Host "`nBuild complete: $SrcBundle" -ForegroundColor Green
    Write-Host "Bundle size  : ${SizeMB} MB"

    exit 0

} finally {
    Pop-Location
}
