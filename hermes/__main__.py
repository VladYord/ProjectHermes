"""Hermes entry point — python -m hermes"""

from __future__ import annotations

import argparse
import io
import os
import socket
import ssl
import sys
from pathlib import Path

# ── PyInstaller frozen-bundle detection ─────────────────────────────────────
# When running as a packaged executable (PyInstaller one-file), set env vars
# BEFORE any library imports so Tesseract and other tools can locate their data.
if getattr(sys, 'frozen', False):
    _meipass = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    os.environ.setdefault('TESSDATA_PREFIX', os.path.join(_meipass, 'tessdata'))
    os.environ.setdefault('HERMES_PACKAGED', '1')
    
    # Patch None streams so libraries don't crash with isatty() errors.
    # Skip if MCP mode is active — MCP needs real stdio.
    if os.environ.get('HERMES_MCP') != '1':
        # Redirect stderr to a log file in the app-data directory so startup
        # crashes are visible when console=False hides the terminal.
        try:
            from hermes.config_manager import get_app_data_dir
            _log_dir = get_app_data_dir()
            _err_log = _log_dir / "backend-error.log"
            _err_fh = open(_err_log, "a", encoding="utf-8")
        except Exception:
            _err_fh = open(os.devnull, "w")
        if sys.stdout is None:
            sys.stdout = io.TextIOWrapper(open(os.devnull, "wb"))
        if sys.stderr is None:
            sys.stderr = io.TextIOWrapper(_err_fh)
        else:
            # Also tee stderr to the log file so nothing is lost
            pass
# ─────────────────────────────────────────────────────────────────────────────

# Disable SSL certificate verification globally.
# Required in corporate environments where a proxy presents its own CA cert
# that is not trusted by Python's default certificate store.
# Production fix: set SSL_CERT_FILE to the corporate CA bundle path instead.
ssl._create_default_https_context = ssl._create_unverified_context  # noqa: SLF001


def find_free_port() -> int:
    """Bind to port 0 to let the OS assign a free port, then return it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _safe_stderr(msg: str) -> None:
    """Print to stderr, silently skipping if stderr is None (GUI subsystem)."""
    if sys.stderr is not None:
        print(msg, file=sys.stderr, flush=True)


def write_backend_port_file(port: int) -> None:
    """Persist the chosen packaged-backend port for the Tauri shell fallback."""
    if not os.environ.get('HERMES_PACKAGED'):
        return
    try:
        from hermes.config_manager import get_app_data_dir
        app_dir = get_app_data_dir()
        app_dir.mkdir(parents=True, exist_ok=True)   # ← ensure dir exists
        port_file = app_dir / "backend-port.txt"
        port_file.write_text(f"{port}\n", encoding="utf-8")
        # Write to stderr since stdout may be None
        if sys.stderr is not None:
            print(f"Port file written: {port_file}", file=sys.stderr, flush=True)
    except Exception as exc:
        if sys.stderr is not None:
            print(f"ERROR: Failed to write backend port file: {exc}", file=sys.stderr, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes — Local-first AI knowledge agent")
    parser.add_argument("--host", default=None, help="Server host (overrides config)")
    parser.add_argument("--port", type=int, default=None,
                        help="Server port (overrides config; use 0 for OS-assigned free port)")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--mcp", action="store_true", help="Run as MCP server (stdio)")
    parser.add_argument(
        "--packaged",
        action="store_true",
        help="Running inside a Tauri bundle; redirect data dirs to OS app-data",
    )

    args = parser.parse_args()

    # If launched with --packaged (from Tauri), set the env var so config.py
    # redirects data paths to the OS app-data directory.
    if args.packaged:
        os.environ.setdefault('HERMES_PACKAGED', '1')
    if args.mcp:
        os.environ.setdefault('HERMES_MCP', '1')

    from hermes.config import HermesConfig  # always available as safe default

    cfg = None

    # Load config (must happen before other imports that use get_config)
    try:
        from hermes.config import load_config
        import hermes.config as config_module

        config_module._config = load_config(args.config)
        cfg = config_module._config

        # Apply CLI overrides
        if args.host:
            cfg.server.host = args.host
        if args.port is not None:
            if args.port == 0:
                cfg.server.port = find_free_port()
            else:
                cfg.server.port = args.port
    except Exception as e:
        # If config fails, use reasonable defaults and still write port file
        # so Tauri knows we're alive (even if stdout capture fails).
        _safe_stderr(f"ERROR: Config loading failed: {e}")
        try:
            from hermes.config import get_config
            cfg = get_config()
            cfg.server.port = find_free_port()
        except Exception  as e2:
            # Final fallback if everything else fails
            _safe_stderr(f"ERROR: Fallback config failed: {e2}")
            cfg = HermesConfig()
            cfg.server.port = find_free_port()
    
    # Print PORT= before starting so Tauri (or any parent process) can read it.
    # Format is exactly "PORT=<number>\n" — Tauri parses this line from stdout.
    # When packaged with console=False (GUI subsystem), sys.stdout may be None;
    # in that case the port-file fallback is the only handshake mechanism.
    if sys.stdout is not None:
        sys.stdout.write(f"PORT={cfg.server.port}\n")
        sys.stdout.flush()
    write_backend_port_file(cfg.server.port)

    from hermes.log_setup import setup_logging
    setup_logging()

    if args.mcp:
        # MCP server mode (stdio)
        from hermes.mcp_server import run_mcp_server
        run_mcp_server()
    else:
        # HTTP server mode
        import uvicorn
        if getattr(sys, 'frozen', False):
            # PyInstaller frozen binary: uvicorn cannot load modules by string
            # because importlib can't navigate the frozen archive by name.
            # Import the app object directly so uvicorn receives it as an object.
            from hermes.server import app as _app  # noqa: PLC0415
            uvicorn.run(
                _app,
                host=cfg.server.host,
                port=cfg.server.port,
                log_level="info",
                log_config=None, # prevents isatty() crash
            )
        else:
            # Normal (source / venv) mode: string form enables uvicorn --reload
            uvicorn.run(
                "hermes.server:app",
                host=cfg.server.host,
                port=cfg.server.port,
                log_level="info",
            )


if __name__ == "__main__":
    main()
