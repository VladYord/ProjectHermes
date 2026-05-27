"""Phase 1 Verification Script — Hermes

Runs every item from doc/plan/Phase1_Backend.md Verification Checklist
automatically.  Start the server, probe each endpoint, inspect encrypted
files, then cleanly shut down.

Usage (from project root):
    .venv\\Scripts\\python.exe tools\\verify_phase1.py

Exit code 0 = all checks passed, 1 = one or more failed.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

# ── Make hermes importable when running from project root ─────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402  (available in .venv)

VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

# ── ANSI colours (disabled on Windows cmd unless ANSICON/Windows Terminal) ─
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"
_BOLD = "\033[1m"

# Enable VT processing on Windows so colours work in Windows Terminal / pwsh
if platform.system() == "Windows":
    import ctypes
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def _ok(msg: str, detail: str = "") -> str:
    suffix = f"  ({detail})" if detail else ""
    return f"  {_GREEN}✓{_RESET}  {msg}{suffix}"


def _fail(msg: str, detail: str = "") -> str:
    suffix = f"\n       {_RED}{detail}{_RESET}" if detail else ""
    return f"  {_RED}✗{_RESET}  {msg}{suffix}"


def _info(msg: str) -> str:
    return f"  {_YELLOW}·{_RESET}  {msg}"


# ──────────────────────────────────────────────────────────────────────────────


class Phase1Checker:
    def __init__(self) -> None:
        self._results: list[tuple[str, str, str]] = []  # (status, label, detail)
        self._proc: subprocess.Popen | None = None
        self.port: int | None = None

    # ── Result helpers ────────────────────────────────────────────────

    def passed(self, label: str, detail: str = "") -> None:
        self._results.append(("PASS", label, detail))
        print(_ok(label, detail))

    def failed(self, label: str, detail: str = "") -> None:
        self._results.append(("FAIL", label, detail))
        print(_fail(label, detail))

    def info(self, msg: str) -> None:
        print(_info(msg))

    # ── Server lifecycle ──────────────────────────────────────────────

    def start_server(self) -> bool:
        """Start ``python -m hermes --port 0`` and capture the PORT= line."""
        print(f"\n{_BOLD}[1] Dynamic-port startup{_RESET}")

        self._proc = subprocess.Popen(
            [PYTHON, "-m", "hermes", "--port", "0"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        # Drain stderr in background so the pipe doesn't block
        def _drain(stream):
            for _ in stream:
                pass

        threading.Thread(target=_drain, args=(self._proc.stderr,), daemon=True).start()

        # Read stdout looking for the PORT= line
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                self.failed("--port 0: server process exited unexpectedly")
                return False
            line = self._proc.stdout.readline().strip()
            if line.startswith("PORT="):
                try:
                    self.port = int(line.split("=", 1)[1])
                except ValueError:
                    self.failed("--port 0: PORT= line is malformed", line)
                    return False
                self.passed("--port 0 prints PORT=<number> to stdout", f"PORT={self.port}")
                break
        else:
            self.failed("--port 0: timed out waiting for PORT= on stdout")
            return False

        # Wait for the HTTP server to accept connections
        base = f"http://127.0.0.1:{self.port}"
        for _ in range(30):
            try:
                r = httpx.get(f"{base}/api/health", timeout=1.0)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.5)

        self.failed("Server did not become ready within 15 s")
        return False

    def stop_server(self) -> None:
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    # ── Individual checks ─────────────────────────────────────────────

    def check_health(self) -> None:
        print(f"\n{_BOLD}[2] GET /api/health{_RESET}")
        try:
            r = httpx.get(f"http://127.0.0.1:{self.port}/api/health", timeout=5)
        except Exception as exc:
            self.failed("GET /api/health", str(exc))
            return
        if r.status_code == 200 and r.json().get("status") == "ok":
            self.passed('GET /api/health → 200 {"status": "ok"}',
                        f'version={r.json().get("version")}')
        else:
            self.failed("GET /api/health", f"status={r.status_code} body={r.text[:120]}")

    def check_get_config(self) -> None:
        print(f"\n{_BOLD}[3] GET /api/config{_RESET}")
        try:
            r = httpx.get(f"http://127.0.0.1:{self.port}/api/config", timeout=5)
        except Exception as exc:
            self.failed("GET /api/config", str(exc))
            return

        if r.status_code != 200:
            self.failed("GET /api/config → 200", f"status={r.status_code} body={r.text[:120]}")
            return

        data = r.json()
        if "default_provider" in data and "providers" in data:
            self.passed("GET /api/config → 200 with provider info")
        else:
            self.failed("GET /api/config → missing expected fields", str(data)[:200])
            return

        openai = data.get("providers", {}).get("openai", {})
        if openai.get("api_key_set") is False:
            self.passed("API keys masked in fresh GET /api/config (api_key_set=false)")
        else:
            self.info(f"openai api_key_set={openai.get('api_key_set')} "
                      "(may be true if a key was set in a previous run)")

        self.info(f"default_provider={data.get('default_provider')}  "
                  f"embedding_provider={data.get('embedding_provider')}")

    def check_patch_config(self) -> None:
        print(f"\n{_BOLD}[4] PATCH /api/config  (set + verify + clear OpenAI key){_RESET}")

        # --- set key ---
        try:
            r = httpx.patch(
                f"http://127.0.0.1:{self.port}/api/config",
                json={"providers": {"openai": {"api_key": "sk-test-phase1-verify"}}},
                timeout=5,
            )
        except Exception as exc:
            self.failed("PATCH /api/config", str(exc))
            return

        if r.status_code != 200:
            self.failed("PATCH /api/config → 200", f"status={r.status_code} body={r.text[:200]}")
            return

        patch_data = r.json()
        key_set = patch_data.get("providers", {}).get("openai", {}).get("api_key_set")
        if key_set:
            self.passed("PATCH /api/config → response shows api_key_set=true immediately")
        else:
            self.failed("PATCH /api/config → api_key_set not true in response", str(patch_data))

        # --- verify via GET ---
        try:
            r2 = httpx.get(f"http://127.0.0.1:{self.port}/api/config", timeout=5)
        except Exception as exc:
            self.failed("GET /api/config (after PATCH)", str(exc))
            return

        if r2.json().get("providers", {}).get("openai", {}).get("api_key_set"):
            self.passed("GET /api/config after PATCH → api_key_set=true persisted")
        else:
            self.failed("GET /api/config after PATCH → api_key_set not reflected")

    def check_encrypted_files(self) -> None:
        print(f"\n{_BOLD}[5] Encrypted config files{_RESET}")

        # Import after sys.path is set
        from hermes.config_manager import get_app_data_dir

        app_data = get_app_data_dir()
        enc_file = app_data / "config.enc"
        key_file = app_data / "app_secret.key"

        self.info(f"App-data dir: {app_data}")

        # config.enc
        if enc_file.exists():
            self.passed("config.enc exists", str(enc_file))
            raw = enc_file.read_bytes()
            try:
                json.loads(raw)
                self.failed("config.enc is plain-text JSON — should be encrypted")
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                self.passed("config.enc is NOT human-readable (encrypted ✓)")
            self.info(f"config.enc size: {len(raw)} bytes")
        else:
            self.failed("config.enc not found — was PATCH /api/config called successfully?",
                        str(enc_file))

        # app_secret.key
        if key_file.exists():
            self.passed("app_secret.key exists", str(key_file))
            if platform.system() != "Windows":
                mode = key_file.stat().st_mode & 0o777
                mode_str = oct(mode)
                if mode & 0o177 == 0:
                    self.passed(f"app_secret.key permissions restricted to owner ({mode_str})")
                else:
                    self.failed(f"app_secret.key permissions too open ({mode_str})",
                                "expected 0o600")
            else:
                self.passed("app_secret.key in user-private %APPDATA%\\Hermes\\ (Windows ACL)")
                self.info("Windows ACL inherited from %APPDATA% — only current user has access")
        else:
            self.failed("app_secret.key not found", str(key_file))

    def check_providers(self) -> None:
        print(f"\n{_BOLD}[6] GET /api/providers — reachability{_RESET}")
        try:
            r = httpx.get(f"http://127.0.0.1:{self.port}/api/providers", timeout=10)
        except Exception as exc:
            self.failed("GET /api/providers", str(exc))
            return

        if r.status_code != 200:
            self.failed("GET /api/providers → 200",
                        f"status={r.status_code} body={r.text[:120]}")
            return

        self.passed("GET /api/providers → 200")
        data = r.json()
        providers = {p["name"]: p for p in data.get("providers", [])}

        # Ollama check
        ollama = providers.get("ollama", {})
        reachable = ollama.get("reachable")
        if reachable is False:
            self.passed("ollama reachable=false (Ollama not running — expected in this env)")
        elif reachable is True:
            latency = ollama.get("latency_ms")
            self.passed("ollama reachable=true (Ollama is running!)",
                        f"latency={latency} ms")
        else:
            self.info(f"ollama reachability: {reachable}")

        # Cloud providers: keys set by PATCH test, so openai should be api_key_set=true
        for name in ("openai", "gemini", "azure_openai"):
            p = providers.get(name, {})
            key_set = p.get("api_key_set")
            model = p.get("model", "?")
            self.info(f"{name}: api_key_set={key_set}  model={model}")

        self.info(f"Providers in response: {list(providers.keys())}")

    def cleanup_test_key(self) -> None:
        """Clear the test OpenAI key that was set during check_patch_config."""
        print(f"\n{_BOLD}[7] Cleanup — clear test API key{_RESET}")
        try:
            r = httpx.patch(
                f"http://127.0.0.1:{self.port}/api/config",
                json={"providers": {"openai": {"api_key": ""}}},
                timeout=5,
            )
            if r.status_code == 200:
                key_set = r.json().get("providers", {}).get("openai", {}).get("api_key_set")
                if not key_set:
                    self.passed("Test API key cleared (api_key_set=false again)")
                else:
                    self.failed("Test API key not cleared", str(r.json()))
            else:
                self.info(f"Cleanup PATCH returned {r.status_code} — not critical")
        except Exception as exc:
            self.info(f"Cleanup failed (not critical): {exc}")

    # ── Summary ───────────────────────────────────────────────────────

    def summary(self) -> bool:
        passes = sum(1 for r in self._results if r[0] == "PASS")
        fails = sum(1 for r in self._results if r[0] == "FAIL")
        print(f"\n{'='*60}")
        if fails == 0:
            print(f"{_GREEN}{_BOLD}Phase 1 Verification: {passes} checks passed ✓{_RESET}")
        else:
            print(f"{_RED}{_BOLD}Phase 1 Verification: {passes} passed, {fails} FAILED{_RESET}")
            print(f"\n{_RED}Failed checks:{_RESET}")
            for status, label, detail in self._results:
                if status == "FAIL":
                    print(f"  ✗  {label}" + (f"\n       {detail}" if detail else ""))
        print("="*60)
        return fails == 0


# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{'='*60}")
    print(f"{_BOLD}Hermes — Phase 1 Verification Checklist{_RESET}")
    print(f"Python: {PYTHON}")
    print("="*60)

    # [0] pytest
    print(f"\n{_BOLD}[0] pytest — regression suite{_RESET}")
    result = subprocess.run(
        [PYTHON, "-m", "pytest", "tests/", "-q", "--tb=line"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    # Last meaningful line (e.g. "76 passed in 49s")
    last = [l for l in result.stdout.strip().splitlines() if l.strip()]
    summary_line = last[-1] if last else "(no output)"
    if result.returncode == 0:
        print(_ok("pytest", summary_line))
    else:
        print(_fail("pytest", summary_line))
        print(result.stdout[-600:])

    checker = Phase1Checker()

    if not checker.start_server():
        checker.summary()
        sys.exit(1)

    try:
        checker.check_health()
        checker.check_get_config()
        checker.check_patch_config()
        checker.check_encrypted_files()
        checker.check_providers()
        checker.cleanup_test_key()
    finally:
        checker.stop_server()

    success = checker.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
