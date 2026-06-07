<#
.SYNOPSIS
    Stops stale Hermes dev/build processes that can lock build artifacts.

.DESCRIPTION
    Kills known Hermes/Tauri dev processes when they are running from this
    repository path. This avoids Windows file lock errors during
    `make bundle-backend` / `make bundle-app`.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path

Write-Host "=== Prebuild process cleanup (Windows) ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

$killed = 0

# 1) Kill hermes sidecar processes spawned from this repo's resources path.
# 1) Kill hermes sidecar processes spawned from this repo (resources or target paths).
$srcTauriPath = (Join-Path $ProjectRoot "src-tauri").ToLowerInvariant()
$procs = Get-CimInstance Win32_Process |
    Where-Object {
        $_.ExecutablePath -and
        $_.ExecutablePath.ToLowerInvariant().StartsWith($srcTauriPath) -and
        ($_.Name -like "hermes-server*.exe")
    }

foreach ($p in $procs) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped sidecar lock holder: $($p.Name) (PID $($p.ProcessId))"
        $killed++
    } catch {
        Write-Warning "Could not stop PID $($p.ProcessId): $($_.Exception.Message)"
    }
}

# 2) Stop project-scoped dev processes by command line path.
$projectRootLower = $ProjectRoot.ToLowerInvariant()
$devNames = @("cargo.exe", "node.exe", "npm.exe")

$devProcs = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -and
        ($devNames -contains $_.Name.ToLowerInvariant()) -and
        $_.CommandLine -and
        $_.CommandLine.ToLowerInvariant().Contains($projectRootLower)
    }

foreach ($p in $devProcs) {
    try {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
        Write-Host "Stopped project dev process: $($p.Name) (PID $($p.ProcessId))"
        $killed++
    } catch {
        Write-Warning "Could not stop PID $($p.ProcessId): $($_.Exception.Message)"
    }
}

if ($killed -eq 0) {
    Write-Host "No stale processes found."
} else {
    Write-Host "Stopped $killed process(es)." -ForegroundColor Yellow
}

# 3) Remove stale sidecar copies from Cargo build output and backend dist.
# tauri-build does fs::remove_file(&dest).unwrap() before replacing these files.
# If they are read-only (set by a previous Tauri build) it panics with
# Os { code: 5, kind: PermissionDenied } even with no processes running.
# Deleting them here lets tauri-build start fresh without hitting that unwrap().
$staleSidecarPaths = @(
    # Old onefile format (with target triple)
    (Join-Path $ProjectRoot "backend\dist\hermes-server-x86_64-pc-windows-msvc.exe"),
    (Join-Path $ProjectRoot "src-tauri\target\release\hermes-server.exe"),
    (Join-Path $ProjectRoot "src-tauri\target\release\bundle\nsis\hermes-server.exe"),
    (Join-Path $ProjectRoot "src-tauri\target\release\bundle\msi\hermes-server.exe"),
    (Join-Path $ProjectRoot "src-tauri\resources\hermes-server-x86_64-pc-windows-msvc.exe"),
    # New onedir format (no target triple)
    (Join-Path $ProjectRoot "backend\dist\hermes-server"),
    (Join-Path $ProjectRoot "src-tauri\resources\hermes-server"),
    (Join-Path $ProjectRoot "src-tauri\target\release\hermes-server")
)

foreach ($path in $staleSidecarPaths) {
    if (Test-Path $path) {
        try {
            attrib -R $path | Out-Null
            Remove-Item -Force -Recurse $path -ErrorAction Stop
            Write-Host "Removed stale sidecar copy: $path"
            $killed++
        } catch {
            Write-Warning "Could not remove $path : $($_.Exception.Message)"
        }
    }
}

Write-Host "Prebuild cleanup complete." -ForegroundColor Green
