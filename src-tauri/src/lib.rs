use std::sync::{Arc, Mutex as StdMutex};
use std::{env, fs, path::PathBuf, time::Duration};
use std::process::Command as ProcessCommand;
use tokio::time::sleep;
use tauri::{AppHandle, Emitter, Manager, State};
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
    pub backend_child: Arc<StdMutex<Option<tauri_plugin_shell::process::CommandChild>>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            backend_port: Arc::new(Mutex::new(None)),
            backend_child: Arc::new(StdMutex::new(None)),
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

fn backend_port_file_path() -> Option<PathBuf> {
    let appdata = env::var_os("APPDATA")?;
    Some(PathBuf::from(appdata).join("Hermes").join("backend-port.txt"))
}

fn read_backend_port_file() -> Option<u16> {
    let path = backend_port_file_path()?;
    let content = fs::read_to_string(path).ok()?;
    content.trim().parse::<u16>().ok()
}

async fn publish_backend_port(app: &AppHandle, port: u16) {
    let state = app.state::<AppState>();
    let mut backend_port = state.backend_port.lock().await;
    if backend_port.is_some() {
        return;
    }

    *backend_port = Some(port);
    let _ = app.emit("backend-ready", BackendReadyPayload { port });
    log::info!("✓ Backend sidecar handshake complete: port {port}");
}

fn terminate_backend_child(child: tauri_plugin_shell::process::CommandChild) {
    #[cfg(windows)]
    {
        let pid = child.pid();
        match ProcessCommand::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .status()
        {
            Ok(status) if status.success() => {
                log::info!("Backend sidecar process tree killed on exit (PID {pid}).");
                return;
            }
            Ok(status) => {
                log::warn!("taskkill exited with status {status} for backend PID {pid}; falling back to child.kill()");
            }
            Err(error) => {
                log::warn!("Failed to run taskkill for backend PID {pid}: {error}; falling back to child.kill()");
            }
        }
    }

    if let Err(error) = child.kill() {
        log::warn!("Failed to kill backend sidecar on exit: {error}");
    } else {
        log::info!("Backend sidecar killed on exit.");
    }
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

    if let Some(path) = backend_port_file_path() {
        let _ = fs::remove_file(path);
    }

    let sidecar_cmd = match shell.sidecar("hermes-server") {
        Ok(cmd) => cmd,
        Err(e) => {
            // Expected in dev mode — frontend uses hardcoded port 8000.
            log::warn!("Backend sidecar not found (expected in `cargo tauri dev`): {e}");
            return;
        }
    };

    log::info!("Attempting to spawn backend sidecar with args: --port 0 --packaged");
    
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

    log::info!("Backend sidecar spawned successfully, waiting for PORT= output...");

    let port_file_fallback = {
        let handle = app.clone();
        tauri::async_runtime::spawn(async move {
            for _ in 0..100 {
                if let Some(port) = read_backend_port_file() {
                    publish_backend_port(&handle, port).await;
                    return;
                }
                sleep(Duration::from_millis(100)).await;
            }
            log::warn!("Backend sidecar port file fallback did not resolve within 10s");
        })
    };

    // Persist the child handle so we can kill it on app exit.
    {
        let state = app.state::<AppState>();
        *state.backend_child.lock().expect("backend child mutex poisoned") = Some(child);
    }

    // Stream stdout/stderr; capture the "PORT=N" handshake line.
    let mut port_received = false;
    while let Some(event) = rx.recv().await {
        match event {
            CommandEvent::Stdout(bytes) => {
                let line = String::from_utf8_lossy(&bytes);
                let line = line.trim();
                log::info!("backend stdout: {line}");  // Changed from debug to info for visibility

                if let Some(port_str) = line.strip_prefix("PORT=") {
                    if let Ok(port) = port_str.parse::<u16>() {
                        publish_backend_port(&app, port).await;
                        port_received = true;
                    } else {
                        log::warn!("Failed to parse port from: {port_str}");
                    }
                }
            }
            CommandEvent::Stderr(bytes) => {
                let err_line = String::from_utf8_lossy(&bytes);
                let err_line = err_line.trim();
                if !err_line.is_empty() {
                    log::warn!("backend stderr: {err_line}");  // Changed from debug to warn
                }
            }
            CommandEvent::Terminated(status) => {
                port_file_fallback.abort();
                if !port_received {
                    log::error!("Backend sidecar terminated before sending PORT=: {:?}", status);
                } else {
                    log::info!("Backend sidecar terminated: {:?}", status);
                }
                break;
            }
            _ => {}
        }
    }

    port_file_fallback.abort();
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
        // Spawn the sidecar in a background task — production only.
        // In debug builds (`cargo tauri dev`) the developer starts the backend
        // manually and the frontend connects to hardcoded port 8000.
        if !cfg!(debug_assertions) {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                spawn_backend(handle).await;
            });
        } else {
            log::info!("Dev build: skipping sidecar spawn. \
                Start backend with: .venv\\Scripts\\python.exe -m hermes --port 8000");
        }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Hermes")
        .run(|app_handle, event| {
            // On app exit — kill the sidecar so it doesn't linger.
            if matches!(event, tauri::RunEvent::Exit) {
                let child_arc = app_handle.state::<AppState>().backend_child.clone();
                let child = {
                    let mut guard = child_arc.lock().expect("backend child mutex poisoned");
                    guard.take()
                };

                if let Some(child) = child {
                    terminate_backend_child(child);
                }
            }
        });
}

