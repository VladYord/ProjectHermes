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
}

export const backend = new BackendState();

/** Base URL used by all API calls — updates automatically when port is known. */
export function apiBase(): string {
  return `http://127.0.0.1:${backend.port ?? 8000}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Poll GET /api/health until 200 OK or timeout. Returns null on success, error string on failure. */
async function pollUntilHealthy(timeoutMs = 30_000): Promise<string | null> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${apiBase()}/api/health`);
      if (res.ok) {
        backend.ready = true;
        return null;
      }
    } catch {
      // Backend not yet accepting connections — keep polling
    }
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
    // Browser / plain `npm run dev` — backend started manually
    backend.port = 8000;
    return pollUntilHealthy();
  }

  // Packaged Tauri app — port comes from the Rust sidecar via event
  const { listen } = await import('@tauri-apps/api/event');
  const { invoke } = await import('@tauri-apps/api/core');

  // Fast path: sidecar may have already emitted PORT= before we registered the listener
  try {
    const port = await invoke<number>('get_backend_port');
    backend.port = port;
    return pollUntilHealthy();
  } catch {
    // Not ready yet — fall through to event listener
  }

  return new Promise<string | null>((resolve) => {
    let settled = false;

    listen<{ port: number }>('backend-ready', async (event) => {
      if (settled) return;
      settled = true;
      backend.port = event.payload.port;
      resolve(await pollUntilHealthy());
    });

    // Hard timeout — in case the sidecar fails to start entirely
    setTimeout(() => {
      if (!settled) {
        settled = true;
        resolve('Backend failed to start. Check the application logs in %APPDATA%\\Hermes\\.');
      }
    }, 60_000);
  });
}
