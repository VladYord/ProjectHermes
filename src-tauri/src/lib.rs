use std::sync::Arc;
use tauri::{AppHandle, Manager, State};
use tauri::async_runtime::Mutex;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;

// ---------------------------------------------------------------------------
// Shared app state
// ---------------------------------------------------------------------------

/// Payload emitted to the WebView when the backend sidecar has started.
#[derive(serde::Serialize, Clone)]
struct BackendReadyPayload {
    port: u16,
}

/// Shared mutable state managed by Tauri.
pub struct AppState {
    /// Port the Python backend sidecar is listening on (None until started).
    pub backend_port: Arc<Mutex<Option<u16>>>,
    /// Handle to the running sidecar child — used to kill it on app exit.
    pub backend_child: Arc<Mutex<Option<tauri_plugin_shell::process::CommandChild>>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            backend_port: Arc::new(Mutex::new(None)),
            backend_child: Arc::new(Mutex::new(None)),
        }
    }
}

// ---------------------------------------------------------------------------
// Tauri commands (callable from the frontend)
// ---------------------------------------------------------------------------

/// Return the port the backend sidecar is listening on.
/// Fails with a user-visible error string if the sidecar hasn't started yet.
#[tauri::command]
async fn get_backend_port(state: State<'_, AppState>) -> Result<u16, String> {
    state
        .backend_port
        .lock()
        .await
        .ok_or_else(|| "Backend not ready".into())
}

// ---------------------------------------------------------------------------
// Sidecar lifecycle
// ---------------------------------------------------------------------------

/// Spawn the Python backend sidecar and forward its port to the WebView.
///
/// The sidecar is expected to print `PORT=<number>` on stdout once it is
/// ready to accept connections.  Until that line arrives we keep reading.
///
/// In development (`cargo tauri dev`) the binary will not be present; the
/// shell plugin returns an error and this function returns early — the
/// frontend's dev-mode path uses the manually-started port 8000 instead.
async fn spawn_backend(app: AppHandle) {
    let shell = app.shell();

    let sidecar_cmd = match shell.sidecar("hermes-server") {
        Ok(cmd) => cmd,
        Err(e) => {
            // Expected in dev mode — frontend uses hardcoded port 8000.
            log::warn!("Backend sidecar not found (expected in `cargo tauri dev`): {e}");
            return;
        }
    };

    let (mut rx, child) = match sidecar_cmd
        .args(["--port", "0", "--packaged"])
        .spawn()
    {
        Ok(pair) => pair,
        Err(e) => {
            log::error!("Failed to spawn backend sidecar: {e}");
            return;
        }
    };

    // Persist the child handle so we can kill it on app exit.
    {
        let state = app.state::<AppState>();
        *state.backend_child.lock().await = Some(child);
    }

    // Stream stdout/stderr; capture the "PORT=N" handshake line.
    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(bytes) => {
                let line = String::from_utf8_lossy(&bytes);
                let line = line.trim();
                log::debug!("backend: {line}");

                if let Some(port_str) = line.strip_prefix("PORT=") {
                    if let Ok(port) = port_str.parse::<u16>() {
                        let state = app.state::<AppState>();
                        *state.backend_port.lock().await = Some(port);
                        let _ = app.emit("backend-ready", BackendReadyPayload { port });
                        log::info!("Backend sidecar started on port {port}");
                    }
                }
            }
            CommandEvent::Stderr(bytes) => {
                log::debug!("backend stderr: {}", String::from_utf8_lossy(&bytes).trim());
            }
            CommandEvent::Terminated(status) => {
                log::info!("Backend sidecar terminated: {:?}", status);
                break;
            }
            _ => {}
        }
    }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState::default())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            // Spawn the sidecar in a background task — non-blocking.
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                spawn_backend(handle).await;
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Hermes")
        .run(|app_handle, event| {
            // On app exit — kill the sidecar so it doesn't linger.
            if matches!(event, tauri::RunEvent::Exit) {
                let child_arc = app_handle.state::<AppState>().backend_child.clone();
                tauri::async_runtime::spawn(async move {
                    if let Some(mut child) = child_arc.lock().await.take() {
                        let _ = child.kill();
                        log::info!("Backend sidecar killed on exit.");
                    }
                });
            }
        });
}

