"""Hermes entry point — python -m hermes"""

from __future__ import annotations

import argparse
import os
import socket
import ssl
import sys

# ── PyInstaller frozen-bundle detection ─────────────────────────────────────
# When running as a packaged executable (PyInstaller one-file), set env vars
# BEFORE any library imports so Tesseract and other tools can locate their data.
if getattr(sys, 'frozen', False):
    _meipass = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    os.environ.setdefault('TESSDATA_PREFIX', os.path.join(_meipass, 'tessdata'))
    os.environ.setdefault('HERMES_PACKAGED', '1')
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

    # Load config (must happen before other imports that use get_config)
    from hermes.config import load_config, _config
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

    # Print PORT= before starting so Tauri (or any parent process) can read it.
    # Format is exactly "PORT=<number>\n" — Tauri parses this line from stdout.
    print(f"PORT={cfg.server.port}", flush=True)

    from hermes.logging import setup_logging
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
