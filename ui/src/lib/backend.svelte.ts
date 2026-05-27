/**
 * Backend sidecar port management.
 *
 * Dev mode  (`npm run dev`):  backend runs manually on port 8000;
 *                              we poll health until it responds.
 * Production (Tauri app):      Rust sidecar emits "backend-ready" {port};
 *                              we capture it then poll health.
 */

function isTauri(): boolean {
  return (
    typeof window !== 'undefined' &&
    Boolean((window as { __TAURI_INTERNALS__?: object }).__TAURI_INTERNALS__)
  );
}

class BackendState {
  port = $state<number | null>(null);
  ready = $state(false);
  connected = $state(false);
}

export const backend = new BackendState();

/** Base URL used by all API calls — updates automatically when port is known. */
export function apiBase(): string {
  return `http://127.0.0.1:${backend.port ?? 8000}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

let watchersAttached = false;

async function probeHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${apiBase()}/api/health`);
    return res.ok;
  } catch {
    return false;
  }
}

function attachConnectionWatchers(): void {
  if (watchersAttached || typeof window === 'undefined') return;
  watchersAttached = true;

  const refresh = () => {
    void refreshBackendConnection();
  };

  // Re-check when user returns to the app, without background polling noise.
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      refresh();
    }
  });
}

export function setBackendConnected(connected: boolean): void {
  backend.connected = connected;
}

export async function refreshBackendConnection(): Promise<boolean> {
  const ok = await probeHealth();
  backend.connected = ok;
  return ok;
}

/** Poll GET /api/health until 200 OK or timeout. Returns null on success, error string on failure. */
async function pollUntilHealthy(timeoutMs = 30_000): Promise<string | null> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${apiBase()}/api/health`);
      if (res.ok) {
        backend.ready = true;
        backend.connected = true;
        return null;
      }
    } catch {
      // Backend not yet accepting connections — keep polling
    }
    backend.connected = false;
    await sleep(500);
  }
  return 'Timed out (30 s) waiting for backend. Start it manually: python -m hermes --port 8000';
}

/**
 * Initialise the backend connection.
 * Must be called once from `App.svelte` `onMount`.
 * Returns null on success, or an error string that should be shown to the user.
 */
export async function initBackend(): Promise<string | null> {
  if (!isTauri() || import.meta.env.DEV) {
    // Dev mode: backend started manually on port 8000.
    // Skip health polling — the app opens immediately; API calls surface
    // errors inline if the backend is not yet running.
    // Start it with:  .venv\Scripts\python.exe -m hermes --port 8000
    backend.port = 8000;
    backend.ready = true;
    attachConnectionWatchers();
    void refreshBackendConnection();
    return null;
  }

  // Packaged Tauri app — port comes from the Rust sidecar via event
  const { listen } = await import('@tauri-apps/api/event');
  const { invoke } = await import('@tauri-apps/api/core');

  // Fast path: sidecar may have already emitted PORT= before we registered the listener
  try {
    const port = await invoke<number>('get_backend_port');
    backend.port = port;
    const err = await pollUntilHealthy();
    attachConnectionWatchers();
    return err;
  } catch {
    // Not ready yet — fall through to event listener
  }

  return new Promise<string | null>((resolve) => {
    let settled = false;

    listen<{ port: number }>('backend-ready', async (event) => {
      if (settled) return;
      settled = true;
      backend.port = event.payload.port;
      const err = await pollUntilHealthy();
      attachConnectionWatchers();
      resolve(err);
    });

    // Hard timeout — in case the sidecar fails to start entirely
    setTimeout(() => {
      if (!settled) {
        settled = true;
        backend.connected = false;
        resolve('Backend failed to start. Check the application logs in %APPDATA%\\Hermes\\.');
      }
    }, 60_000);
  });
}
