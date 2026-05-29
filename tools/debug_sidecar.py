#!/usr/bin/env python3
"""
Debug script to test sidecar subprocess communication.

This script simulates what the Tauri Rust code does:
1. Spawns hermes-server with --port 0 --packaged
2. Reads stdout/stderr line-by-line
3. Captures the PORT= handshake line

Usage:
    python tools/debug_sidecar.py [--binary path/to/hermes-server.exe]
"""

import argparse
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path


def find_sidecar_binary() -> Path:
    """Search for the hermes-server binary in known locations."""
    candidates = [
        Path("src-tauri/resources/hermes-server-x86_64-pc-windows-msvc.exe"),
        Path("src-tauri/resources/hermes-server.exe"),
        Path("dist/hermes-server.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find hermes-server binary. Tried: {', '.join(str(c) for c in candidates)}\n"
        "Run: make bundle-backend"
    )


def enqueue_output(stream, prefix, output_queue):
    for line in iter(stream.readline, ""):
        output_queue.put((prefix, line.rstrip("\n\r")))
    stream.close()
    output_queue.put((prefix, None))


def main():
    parser = argparse.ArgumentParser(
        description="Debug sidecar subprocess communication"
    )
    parser.add_argument(
        "--binary",
        type=Path,
        help="Path to hermes-server binary (auto-detected if not provided)",
    )
    args = parser.parse_args()

    binary = args.binary or find_sidecar_binary()
    print(f"Testing sidecar binary: {binary.resolve()}")
    print(f"Binary exists: {binary.exists()}")
    print()

    try:
        print(f"Spawning: {binary} --port 0 --packaged")
        proc = subprocess.Popen(
            [str(binary), "--port", "0", "--packaged"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        print(f"Process started (PID: {proc.pid})")
        print()

        output_queue = queue.Queue()
        stdout_thread = threading.Thread(
            target=enqueue_output,
            args=(proc.stdout, "stdout", output_queue),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=enqueue_output,
            args=(proc.stderr, "stderr", output_queue),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        port = None
        first_port_time = None
        timeout_sec = 30
        start_time = time.time()
        active_streams = {"stdout": True, "stderr": True}

        print(f"Waiting for PORT= output (timeout = {timeout_sec} seconds)...")
        print("-" * 70)

        while (active_streams["stdout"] or active_streams["stderr"]) and time.time() - start_time < timeout_sec:
            try:
                prefix, line = output_queue.get(timeout=0.5)
            except queue.Empty:
                if proc.poll() is not None and output_queue.empty():
                    break
                continue

            if line is None:
                active_streams[prefix] = False
                continue

            print(f"{prefix.upper()}: {line}")

            if prefix == "stdout" and line.startswith("PORT=") and port is None:
                port_str = line.split("=", 1)[1]
                try:
                    port = int(port_str)
                    first_port_time = time.time()
                    print()
                    print(f"✓ SUCCESS: Captured PORT={port}")
                except ValueError:
                    print(f"✗ Failed to parse PORT value: {port_str}")

        if port is None:
            if proc.poll() is not None:
                print()
                print(f"✗ Process exited before emitting PORT= (exit code: {proc.returncode})")
            else:
                print()
                print(f"✗ TIMEOUT: PORT= line not received within {timeout_sec} seconds")
            proc.terminate()
            print("Use the remaining logs above to diagnose startup failures.")
            return

        # Give the backend a few seconds to bind after the PORT line.
        max_wait = 20
        wait_start = time.time()
        connected = False
        print()
        print(f"Waiting up to {max_wait}s for backend to accept connections on port {port}...")
        while time.time() - wait_start < max_wait:
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    connected = True
                    break
            time.sleep(0.5)

        if connected:
            print(f"✓ Port {port} is accepting connections")
        else:
            print(f"✗ Port {port} is not accepting connections after {max_wait}s")
            print("Continuing to capture any final backend output for 10 more seconds...")
            end_watch = time.time() + 10
            while time.time() < end_watch:
                try:
                    prefix, line = output_queue.get(timeout=0.5)
                except queue.Empty:
                    if proc.poll() is not None and output_queue.empty():
                        break
                    continue
                if line is None:
                    active_streams[prefix] = False
                    continue
                print(f"{prefix.upper()}: {line}")

        terminated_by_script = False
        if proc.poll() is None:
            proc.terminate()
            terminated_by_script = True
            proc.wait(timeout=5)

        if proc.returncode is not None and proc.returncode != 0:
            if terminated_by_script:
                print()
                print(f"Note: backend was terminated intentionally by this debug script (exit code {proc.returncode}).")
            else:
                print()
                print(f"✗ Backend process exited with code {proc.returncode}")
        print("Debug complete.")

    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print("Interrupted by user")
        proc.terminate()


if __name__ == "__main__":
    main()
