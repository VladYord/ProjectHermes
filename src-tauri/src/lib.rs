use std::process::Stdio;
use std::sync::{Arc, Mutex as StdMutex};
use std::{env, fs, path::PathBuf, time::Duration};
#[cfg(windows)]
use std::process::Command as ProcessCommand;
#[cfg(unix)]
use std::process::Command as ProcessCommand;
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::Command as TokioCommand;
use tokio::time::sleep;
use tauri::{AppHandle, Emitter, Manager, State};
use tauri::async_runtime::Mutex;

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
    /// Process id of the running backend sidecar.
    pub backend_pid: Arc<StdMutex<Option<u32>>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            backend_port: Arc::new(Mutex::new(None)),
            backend_pid: Arc::new(StdMutex::new(None)),
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

fn terminate_backend_process(pid: u32) {
    #[cfg(windows)]
    {
        match ProcessCommand::new("taskkill")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .status()
        {
            Ok(status) if status.success() => {
                log::info!("Backend sidecar process tree killed on exit (PID {pid}).");
                return;
            }
            Ok(status) => {
                log::warn!("taskkill exited with status {status} for backend PID {pid}");
            }
            Err(error) => {
                log::warn!("Failed to run taskkill for backend PID {pid}: {error}");
            }
        }

        return;
    }

    #[cfg(unix)]
    {
        match ProcessCommand::new("kill")
            .args(["-TERM", &pid.to_string()])
            .status()
        {
            Ok(status) if status.success() => {
                log::info!("Backend sidecar terminated on exit (PID {pid}).");
            }
            Ok(status) => {
                log::warn!("kill exited with status {status} for backend PID {pid}");
            }
            Err(error) => {
                log::warn!("Failed to run kill for backend PID {pid}: {error}");
            }
        }
    }
}

fn backend_executable_name() -> &'static str {
    #[cfg(windows)]
    {
        return "hermes-server.exe";
    }

    #[cfg(not(windows))]
    {
        return "hermes-server";
    }
}

fn backend_executable_path(app: &AppHandle) -> Result<PathBuf, String> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| format!("Cannot resolve resource directory: {e}"))?;
    // resources config is "resources/hermes-server/" which preserves the
    // relative path from src-tauri/, so the binary lives at:
    //   $RESOURCE/resources/hermes-server/hermes-server.exe
    let full_path = resource_dir.join("resources").join("hermes-server").join(backend_executable_name());
    log::warn!("Resolved backend path: {}", full_path.display());
    log::warn!("Resource dir: {}", resource_dir.display());
    Ok(full_path)
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
    if let Some(path) = backend_port_file_path() {
        let _ = fs::remove_file(path);
    }

    let backend_path = match backend_executable_path(&app) {
        Ok(path) => path,
        Err(error) => {
            log::error!("Failed to resolve backend executable path: {error}");
            return;
        }
    };

    if !backend_path.exists() {
        log::error!("Backend sidecar executable not found at {}", backend_path.display());
        return;
    }

    log::info!(
        "Attempting to spawn backend sidecar: {} --port 0 --packaged",
        backend_path.display()
    );

    let mut child = match TokioCommand::new(&backend_path)
        .args(["--port", "0", "--packaged"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(e) => {
            log::error!("Failed to spawn backend sidecar: {e}");
            return;
        }
    };

    log::info!("Backend sidecar spawned successfully, waiting for PORT= output...");

    let fallback_timeout = Duration::from_secs(60);
    let port_file_fallback = {
        let handle = app.clone();
        tauri::async_runtime::spawn(async move {
            let deadline = tokio::time::Instant::now() + fallback_timeout;
            while tokio::time::Instant::now() < deadline {
                if let Some(port) = read_backend_port_file() {
                    log::info!("Backend handshake via port file: port {port}");
                    publish_backend_port(&handle, port).await;
                    return;
                }
                sleep(Duration::from_millis(200)).await;
            }
            log::error!(
                "Backend sidecar port file fallback did not resolve within {}s",
                fallback_timeout.as_secs()
            );
            // Log the app-data contents for debugging
            if let Some(dir) = backend_port_file_path().and_then(|p| p.parent().map(|d| d.to_path_buf())) {
                match std::fs::read_dir(&dir) {
                    Ok(entries) => {
                        for entry in entries.flatten() {
                            log::warn!("  AppData entry: {}", entry.path().display());
                        }
                    }
                    Err(e) => log::error!("  Cannot list app-data dir {}: {e}", dir.display()),
                }
            }
        })
    };

    // Persist PID so we can kill it on app exit.
    {
        let state = app.state::<AppState>();
        *state.backend_pid.lock().expect("backend pid mutex poisoned") = child.id();
    }

    if let Some(stdout) = child.stdout.take() {
        let handle = app.clone();
        tauri::async_runtime::spawn(async move {
            let mut lines = BufReader::new(stdout).lines();
            let mut port_found = false;
            while let Ok(Some(line)) = lines.next_line().await {
                let line = line.trim();
                log::info!("backend stdout: {line}");
                if let Some(port_str) = line.strip_prefix("PORT=") {
                    if let Ok(port) = port_str.parse::<u16>() {
                        port_found = true;
                        publish_backend_port(&handle, port).await;
                    }
                }
            }
            if !port_found {
                log::error!("Backend stdout pipe closed without PORT= line");
            }
        });
    } else {
        log::warn!("Backend stdout is None (expected with console=False)");
    }

    if let Some(stderr) = child.stderr.take() {
        tauri::async_runtime::spawn(async move {
            let mut lines = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                let line = line.trim();
                if !line.is_empty() {
                    log::warn!("backend stderr: {line}");
                }
            }
        });
    }

    let handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let status = child.wait().await;
        port_file_fallback.abort();

        {
            let state = handle.state::<AppState>();
            *state.backend_pid.lock().expect("backend pid mutex poisoned") = None;
        }

        match status {
            Ok(status) => {
                log::warn!("Backend sidecar terminated: {status}");
            }
            Err(error) => {
                log::error!("Backend sidecar wait failed: {error}");
            }
        }
    });
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
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(if cfg!(debug_assertions) {
                        log::LevelFilter::Info
                    } else {
                        log::LevelFilter::Warn
                    })
                    .build(),
            )?;
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
                let pid_arc = app_handle.state::<AppState>().backend_pid.clone();
                let pid = {
                    let mut guard = pid_arc.lock().expect("backend pid mutex poisoned");
                    guard.take()
                };

                if let Some(pid) = pid {
                    terminate_backend_process(pid);
                }
            }
        });
}

