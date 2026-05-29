<#
.SYNOPSIS
    Copy the built backend binary from backend/dist/ to src-tauri/resources/.

.DESCRIPTION
    This script runs AFTER `build-backend.ps1` completes successfully.
    It copies the bundled Python executable from backend/dist/ to src-tauri/resources/
    so that Tauri can bundle it as a sidecar.

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
    $Triple      = "x86_64-pc-windows-msvc"
    $SrcDir      = Join-Path $ProjectRoot "backend\dist"
    $SrcExe      = Join-Path $SrcDir "hermes-server-$Triple.exe"
    $ResourceDir = Join-Path $ProjectRoot "src-tauri\resources"
    $DestExe     = Join-Path $ResourceDir "hermes-server-$Triple.exe"

    Write-Host "=== Copy backend binary to Tauri resources ===" -ForegroundColor Cyan

    # ── Verify source exists
    if (-not (Test-Path $SrcExe)) {
        Write-Error "Source binary not found: $SrcExe`nRun 'make bundle-backend' first."
    }

    Write-Host "Source : $SrcExe"
    Write-Host "Dest   : $DestExe"

    # ── Ensure destination directory exists
    New-Item -ItemType Directory -Force -Path $ResourceDir | Out-Null

    # ── Remove old destination (clear read-only bit first to avoid Windows errors)
    if (Test-Path $DestExe) {
        try {
            attrib -R $DestExe | Out-Null
            Remove-Item $DestExe -Force -ErrorAction Stop
            Write-Host "Removed old copy: $DestExe"
        } catch {
            Write-Warning "Could not remove old copy: $($_.Exception.Message)"
        }
    }

    # ── Copy the binary
    Copy-Item $SrcExe $DestExe -Force
    Write-Host "Copied to resources." -ForegroundColor Green

    $SizeMB = [math]::Round((Get-Item $DestExe).Length / 1MB, 1)
    Write-Host "Binary size: ${SizeMB} MB"

    Write-Host "Ready for 'cargo tauri build'" -ForegroundColor Green
    exit 0

} finally {
    Pop-Location
}
