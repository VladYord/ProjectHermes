"""
Dev stub — satisfies Tauri's build-time sidecar resource check.

When cargo tauri dev spawns this binary it prints PORT=8000 and exits.
The Svelte frontend takes the DEV branch in initBackend() anyway (hardcoded
port 8000, health-polling the manually-started Python backend), so this
output is effectively ignored.

Do NOT use as a replacement for the real backend.
Build the real sidecar with: make bundle-backend
"""
import sys

print("PORT=8000", flush=True)
sys.exit(0)
