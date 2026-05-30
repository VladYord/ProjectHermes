# Phase 5 — Tauri Integration

**Status:** � Complete  
**Depends on:** [Phase4_Settings.md](Phase4_Settings.md) 🟢  
**Next phase:** [Phase6_BuildPipeline.md](Phase6_BuildPipeline.md)

---

## Goal

Wire the Tauri shell fully to the Python backend sidecar:
- Tauri spawns the Python sidecar on launch and kills it on exit
- The dynamic port printed by the sidecar is captured and passed to the Svelte frontend
- All API calls use the dynamic port (not hardcoded `8000`)
- Native file dialog replaces HTML `<input type="file">` for document upload
- A loading screen is shown while the sidecar starts up
- External links (Ollama guide, API key guides) open in the system browser

After this phase the app runs end-to-end entirely from the Tauri shell — no separate terminal needed.

---

## Sidecar Lifecycle Diagram

```
Tauri Launch
    │
    ▼
spawn_backend()
    │
    ├─► Start hermes-server sidecar with args: ["--port", "0", "--packaged"]
    │
    ├─► Read stdout line by line
    │       └─► Match r"PORT=(\d+)"  →  store port in AppState
    │
    ├─► Emit event "backend-ready" to Svelte WebView
    │
    ▼
Svelte receives "backend-ready" { port: 8765 }
    │
    ▼
All API calls use http://127.0.0.1:{port}/api/...
    │
    ▼
Window Close Event
    │
    └─► Kill sidecar process  →  Exit
```

---

## Steps

### 5.1 — `src-tauri/src/main.rs` — Sidecar spawn + port bridge

```rust
use std::sync::Arc;
use tauri::async_runtime::Mutex;
use tauri_plugin_shell::ShellExt;

#[derive(Default)]
struct AppState {
    backend_port: Arc<Mutex<Option<u16>>>,
    backend_pid:  Arc<Mutex<Option<u32>>>,
}

#[tauri::command]
async fn get_backend_port(state: tauri::State<'_, AppState>) -> Result<u16, String> {
    let port = state.backend_port.lock().await;
    port.ok_or_else(|| "Backend not ready".to_string())
}
```

`spawn_backend()` function:
1. Build sidecar command: `hermes-server --port 0 --packaged`
2. Set env var `HERMES_PACKAGED=1`
3. Spawn with `stdout: Piped`
4. Spawn a thread to read stdout lines
5. Regex-match `PORT=(\d+)` → store in `AppState.backend_port`
6. Emit Tauri event `"backend-ready"` with `{ port }` to all windows
7. Store PID in `AppState.backend_pid`

On `on_window_event(WindowEvent::Destroyed)`:
- Lock `backend_pid`, kill the process

### 5.2 — Register sidecar in `src-tauri/tauri.conf.json`

```json
{
  "bundle": {
    "externalBin": [
      "resources/hermes-server"
    ]
  },
  "plugins": {
    "shell": {
      "sidecar": true,
      "scope": [
        {
          "name": "resources/hermes-server",
          "sidecar": true,
          "args": true
        }
      ]
    }
  }
}
```

> **Note:** During Phase 5 development, the sidecar binary does not exist yet (built in Phase 6).
> For dev testing: start the Python backend manually in a separate terminal and point to `http://localhost:8000`.
> The sidecar wiring is tested end-to-end in Phase 6.

### 5.3 — `ui/src/lib/backend.ts` — Dynamic port store

```typescript
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

export let backendPort = $state<number | null>(null);
export let backendReady = $state(false);

// Called once at app startup
export async function initBackend(): Promise<void> {
  // Listen for backend-ready event from Rust
  await listen<{ port: number }>('backend-ready', (event) => {
    backendPort = event.payload.port;
    backendReady = true;
  });

  // In dev mode: backend port is hardcoded 8000 and backend starts manually
  if (import.meta.env.DEV) {
    backendPort = 8000;
    backendReady = true;
  }
}

export function apiBase(): string {
  return `http://127.0.0.1:${backendPort}`;
}
```

### 5.4 — Update `ui/src/lib/api/client.ts` — Use dynamic base URL

```typescript
import { apiBase } from '$lib/backend';

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${apiBase()}${path}`;
  // ... rest of implementation
}
```

### 5.5 — Loading screen in `ui/src/App.svelte`

While `!backendReady`:
- Show centered loading screen: Hermes logo + "Starting..." + animated spinner
- Poll `GET /api/health` every 500ms as backup (in case event was missed)
- Timeout after 30s: show error screen "Failed to start — check logs"

When `backendReady`:
- Fade out loading screen, show main app layout

### 5.6 — Replace HTML file picker with Tauri dialog

Update `UploadButton.svelte`:

```typescript
import { open } from '@tauri-apps/plugin-dialog';

async function pickFiles() {
  const paths = await open({
    multiple: true,
    filters: [{
      name: 'Supported Documents',
      extensions: ['pdf','txt','md','docx','py','js','ts','java','c','cpp','h','cs','go','rs','png','jpg','jpeg','tiff','bmp']
    }]
  });
  if (!paths) return;
  // paths is string[] — read each as File and upload
}
```

Use Tauri's `fs` plugin to read file bytes, create a `Blob`, upload via `POST /api/ingest/upload`.

### 5.7 — External links via Tauri shell

Update `ApiKeyGuides.svelte` and `OllamaStatus.svelte` to open external links:

```typescript
import { open } from '@tauri-apps/plugin-shell';

// Replace window.open(url) with:
await open(url);  // opens in system default browser
```

### 5.8 — App data directory

Update `ui/src/App.svelte` startup to call backend and confirm app-data dir is writable:

The backend (`config_manager.py`) handles this automatically. No frontend action needed beyond confirming `GET /api/health` returns `"status": "ok"`.

---

## Files Created

| File | Purpose |
|---|---|
| `ui/src/lib/backend.ts` | Dynamic port state + `apiBase()` helper |

## Files Modified

| File | Change |
|---|---|
| `src-tauri/src/main.rs` | Sidecar spawn, port capture, AppState, `get_backend_port` command |
| `src-tauri/tauri.conf.json` | Register sidecar in `externalBin`, shell scope |
| `src-tauri/Cargo.toml` | Add `tauri_plugin_shell` dependency (already added in Phase 0, now used) |
| `ui/src/App.svelte` | Loading screen, `initBackend()` on mount |
| `ui/src/lib/api/client.ts` | Use `apiBase()` instead of hardcoded URL |
| `ui/src/lib/components/UploadButton.svelte` | Replace HTML file input with Tauri `dialog.open()` |
| `ui/src/lib/components/ApiKeyGuides.svelte` | `shell.open()` for external links |
| `ui/src/lib/components/OllamaStatus.svelte` | `shell.open()` for Ollama download link |

---

## Testing Strategy (Phase 5 dev mode)

Since the sidecar binary does not exist yet:
1. Start Python backend manually: `python -m hermes --port 8000`
2. In `backend.ts` dev mode check: `backendPort = 8000; backendReady = true`
3. Run `cargo tauri dev` — all features work against the manually started backend
4. Sidecar spawn code is compiled and ready but only exercises when the binary exists (Phase 6)

---

## Verification Checklist

- [x] `cargo tauri dev` opens app with loading screen
- [x] Loading screen disappears when backend health check passes
- [x] All chat, document, settings features work via dynamic port in dev mode
- [x] Click "Add Documents" → native OS file picker opens (not HTML input)
- [x] Selected files are uploaded and ingested correctly
- [x] "Get Key →" buttons in ApiKeyGuides open system browser (not in-app)
- [x] Ollama setup guide link opens in system browser
- [ ] Closing Tauri window: sidecar process terminates (check Task Manager / Activity Monitor)

---

## Open Questions

- What happens if the sidecar crashes after start? **Recommendation: show an error overlay with "Restart" button that re-invokes `spawn_backend()`.**
- Should the loading screen show the sidecar startup log? **Recommendation: no** — keep it clean; logs go to `APP_DATA/hermes/hermes.log`.

---

## Completion Notes

> Fill in after phase is completed:
> - Date completed:
> - Issues encountered:
> - Deviations from plan:
