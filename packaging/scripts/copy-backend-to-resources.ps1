<#
.SYNOPSIS
    Copy the built backend bundle from backend/dist/ to src-tauri/resources/.

.DESCRIPTION
    This script runs AFTER `build-backend.ps1` completes successfully.
    It copies the bundled Python sidecar directory from backend/dist/ to
    src-tauri/resources/ so the app can launch it from bundled resources.

    This separation prevents file-locking issues on Windows where PyInstaller is
    writing to one directory while Tauri is trying to read from the resources folder.

.EXAMPLE
    .\packaging\scripts\copy-backend-to-resources.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
Push-Location $ProjectRoot

try {
    $SrcDir      = Join-Path $ProjectRoot "backend\dist"
    $SrcBundle   = Join-Path $SrcDir "hermes-server"
    $ResourceDir = Join-Path $ProjectRoot "src-tauri\resources"
    $DestBundle  = Join-Path $ResourceDir "hermes-server"
    $DestExe     = Join-Path $DestBundle "hermes-server.exe"

    Write-Host "=== Copy backend binary to Tauri resources ===" -ForegroundColor Cyan

    # ── Verify source exists
    if (-not (Test-Path $SrcBundle)) {
        Write-Error "Source bundle not found: $SrcBundle`nRun 'make bundle-backend' first."
    }

    Write-Host "Source : $SrcBundle"
    Write-Host "Dest   : $DestBundle"

    # ── Ensure destination directory exists
    New-Item -ItemType Directory -Force -Path $ResourceDir | Out-Null

    # ── Remove old destination bundle
    if (Test-Path $DestBundle) {
        try {
            Remove-Item $DestBundle -Recurse -Force -ErrorAction Stop
            Write-Host "Removed old copy: $DestBundle"
        } catch {
            Write-Error "Could not remove old copy: $($_.Exception.Message)`nRun 'make prebuild-stop' and retry."
        }
    }

    # ── Copy the bundle
    Copy-Item $SrcBundle $DestBundle -Recurse -Force
    Write-Host "Copied bundle to resources." -ForegroundColor Green

    if (-not (Test-Path $DestExe)) {
        Write-Error "Copied bundle missing executable: $DestExe"
    }

    $Bytes = (Get-ChildItem $DestBundle -Recurse -File | Measure-Object -Property Length -Sum).Sum
    $SizeMB = [math]::Round($Bytes / 1MB, 1)
    Write-Host "Bundle size: ${SizeMB} MB"

    Write-Host "Ready for 'cargo tauri build'" -ForegroundColor Green
    exit 0

} finally {
    Pop-Location
}
