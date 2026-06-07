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

const PACKAGED_BACKEND_STARTUP_TIMEOUT_MS = 180_000;

class BackendState {
  port = $state<number | null>(null);
  ready = $state(false);
  connected = $state(false);
  startupPhase = $state('Booting UI...');
}

export const backend = new BackendState();

/** Base URL used by all API calls — updates automatically when port is known. */
export function apiBase(): string {
  return `http://127.0.0.1:${backend.port ?? 8000}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithTimeout(input: string, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(input, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function invokeWithTimeout<T>(
  invoke: <R>(command: string, args?: Record<string, unknown>) => Promise<R>,
  command: string,
  timeoutMs: number,
): Promise<T> {
  return await Promise.race([
    invoke<T>(command),
    new Promise<T>((_, reject) => {
      setTimeout(() => {
        reject(new Error(`${command} timed out after ${timeoutMs}ms`));
      }, timeoutMs);
    }),
  ]);
}

async function waitForBackendPort(
  invoke: <T>(command: string, args?: Record<string, unknown>) => Promise<T>,
  timeoutMs = PACKAGED_BACKEND_STARTUP_TIMEOUT_MS,
): Promise<number | null> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      return await invokeWithTimeout<number>(invoke, 'get_backend_port', 1_000);
    } catch {
      await sleep(250);
    }
  }
  return null;
}

let watchersAttached = false;

async function probeHealth(): Promise<boolean> {
  try {
    const res = await fetchWithTimeout(`${apiBase()}/api/health`, 2_000);
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
  backend.startupPhase = `Waiting for backend health on port ${backend.port ?? 'unknown'}...`;
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetchWithTimeout(`${apiBase()}/api/health`, 2_000);
      if (res.ok) {
        backend.ready = true;
        backend.connected = true;
        backend.startupPhase = `Backend ready on port ${backend.port ?? 'unknown'}`;
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
    backend.startupPhase = 'Connected to dev backend on port 8000';
    attachConnectionWatchers();
    void refreshBackendConnection();
    return null;
  }

  // Packaged Tauri app — port comes from the Rust sidecar via event
  const { listen } = await import('@tauri-apps/api/event');
  const { invoke } = await import('@tauri-apps/api/core');

  let settled = false;
  let resolveReady: ((value: string | null) => void) | null = null;

  backend.startupPhase = 'Waiting for packaged backend port...';

  const finish = async (port: number): Promise<string | null> => {
    if (settled) return null;
    settled = true;
    backend.port = port;
    backend.startupPhase = `Received backend port ${port}; checking health...`;
    const err = await pollUntilHealthy();
    attachConnectionWatchers();
    return err;
  };

  const resolveOnce = (value: string | null): void => {
    if (!resolveReady) return;
    const resolve = resolveReady;
    resolveReady = null;
    resolve(value);
  };

  // Register the listener first to avoid missing the event if the sidecar
  // becomes ready between the invoke() fast path and listener attachment.
  const pendingReady = new Promise<string | null>((resolve) => {
    resolveReady = resolve;
    void listen<{ port: number }>('backend-ready', async (event) => {
      const err = await finish(event.payload.port);
      resolveOnce(err);
    });
  });

  // Fast path: sidecar may have already emitted PORT= before we registered the listener
  try {
    const port = await invokeWithTimeout<number>(invoke, 'get_backend_port', 1_000);
    return await finish(port);
  } catch {
    backend.startupPhase = 'Backend port not ready yet; waiting for event or retry...';
    // Not ready yet — fall back to waiting for the port to become queryable.
  }

  void (async () => {
    const port = await waitForBackendPort(invoke);
    if (port !== null) {
      const err = await finish(port);
      resolveOnce(err);
    }
  })();

  return await Promise.race([
    pendingReady,
    new Promise<string>((resolve) => {
      setTimeout(() => {
        if (!settled) {
          settled = true;
          backend.connected = false;
          resolveReady = null;
          resolve('Backend failed to start. Check the application logs in %APPDATA%\\Hermes\\.');
        }
      }, PACKAGED_BACKEND_STARTUP_TIMEOUT_MS);
    }),
  ]);
}
