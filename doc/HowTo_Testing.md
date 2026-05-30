# How To Test A Bundled Hermes Release

This guide is for testing the result of:

```powershell
make bundle-app
```

It answers two practical questions:

1. Which generated file should you actually run?
2. What should you check when the app opens but gets stuck on `Starting backend...`?

---

## Which file is what

After `make bundle-app`, the important Windows outputs are:

| File | Purpose | Should you run it? |
|---|---|---|
| `src-tauri\target\release\app.exe` | The actual desktop app binary in the build folder | **Yes** for a local smoke test |
| `src-tauri\target\release\bundle\nsis\Hermes_...-setup.exe` | NSIS installer | **Yes** for a real release/install test |
| `src-tauri\target\release\bundle\msi\Hermes_....msi` | MSI installer | **Yes** as an alternative installer test |
| `src-tauri\target\release\hermes-server.exe` | Python backend sidecar copied by Tauri | **No**, not as the main app |
| `backend\dist\hermes-server-...exe` | Intermediate PyInstaller output | **No**, build artifact only |
| `src-tauri\resources\hermes-server-...exe` | Packaging input for Tauri | **No**, packaging artifact only |

### Rule of thumb

- If you want to test the **built app directly**, run **`app.exe`**.
- If you want to test the **installer experience**, run **one installer**: either the NSIS `setup.exe` or the `.msi`.
- Do **not** run `hermes-server.exe` by itself unless you are troubleshooting startup.

---

## Recommended test flow

### Option A — Quick smoke test from the build folder

This is the fastest way to confirm the app itself works before testing the installer.

1. Build:

```powershell
make bundle-app
```

2. Run the desktop app directly:

```powershell
src-tauri\target\release\app.exe
```

3. Expected result:
- splash screen appears briefly
- Hermes opens into the main chat UI
- left sidebar is visible
- document/settings buttons are visible
- app does **not** stay forever on `Starting backend...`

4. Once the UI opens:
- open **Settings**
- confirm the app is responsive
- open **Documents**
- ingest a small `.txt` or `.md` file first
- send a test chat message

### Option B — Full release test through the installer

This is the proper end-to-end release test.

1. Build:

```powershell
make bundle-app
```

2. Pick **one** installer:

Recommended:

```text
src-tauri\target\release\bundle\nsis\Hermes_0.1.0_x64-setup.exe
```

Alternative:

```text
src-tauri\target\release\bundle\msi\Hermes_0.1.0_x64_en-US.msi
```

3. Run the installer.

4. Launch **Hermes** from the Start Menu or the installed shortcut.

5. Expected result:
- Hermes window opens
- backend starts automatically
- chat UI appears
- you do **not** need to start Python manually
- you do **not** run `hermes-server.exe` yourself

---

## What goes where at runtime

In a packaged app:

1. **Tauri app** starts first
2. It launches the packaged sidecar:

```text
hermes-server.exe --port 0 --packaged
```

3. The sidecar prints:

```text
PORT=12345
```

4. Tauri passes that port to the Svelte UI
5. The UI polls:

```text
http://127.0.0.1:12345/api/health
```

6. If `/api/health` returns `200 OK`, the splash screen disappears and the chat window opens

So the critical startup chain is:

```text
app.exe / installed Hermes
  -> starts hermes-server.exe
  -> receives PORT=...
  -> GET /api/health succeeds
  -> main UI appears
```

If any one of those steps fails, the UI can stay on `Starting backend...`.

---

## Short troubleshooting guide

## Problem: You ran all the `.exe` files one by one

That is the wrong test method.

Use this instead:

- run **`app.exe`** for a build-folder smoke test
- or run the **installer** and then launch the installed **Hermes** app
- do **not** manually launch `hermes-server.exe` as the normal app

---

## Problem: `hermes-server.exe` is running, but the UI never leaves `Starting backend...`

That usually means one of these is true:

1. You launched the wrong executable
2. The sidecar started but never printed a valid `PORT=...` line
3. The sidecar printed the port, but `/api/health` never became healthy
4. The sidecar started from a different copy/build than the app you launched
5. The sidecar is failing during startup after launch

### First check: run the correct app

For build-folder testing, run:

```powershell
src-tauri\target\release\app.exe
```

Not:

```powershell
src-tauri\target\release\hermes-server.exe
```

---

## Problem: Need to verify the backend sidecar by itself

Use this only for troubleshooting.

From the build output folder:

```powershell
cd src-tauri\target\release
.\hermes-server.exe --port 0 --packaged
```

Expected output:

```text
PORT=xxxxx
```

and then normal uvicorn/Hermes startup messages.

If you get no `PORT=...`, or the process exits immediately, the sidecar is the problem.

### Then test health manually

Using the printed port:

```powershell
Invoke-WebRequest http://127.0.0.1:xxxxx/api/health | Select-Object -Expand Content
```

Expected response:

```json
{"status":"ok","version":"..."}
```

If that works, the backend itself is fine and the remaining problem is in the Tauri-to-UI startup chain.

---

## Problem: Installer works, but the installed app still hangs on startup

### Check for duplicate copies

Do not mix these during one test:

- installed Hermes from the installer
- `src-tauri\target\release\app.exe`
- manually started `hermes-server.exe`

Test one path at a time.

Recommended clean test:

1. close all Hermes-related processes
2. do not manually run `hermes-server.exe`
3. launch only the installed Hermes app

---

## Problem: Old app data is breaking startup or ingestion

Packaged Hermes stores user data under:

```text
%APPDATA%\Hermes
```

Important contents include:

- `config.enc` — encrypted provider settings
- `app_secret.key` — encryption key for `config.enc`
- `chromadb\` — vector database
- `sessions.db` — saved chat sessions

If you want a completely fresh packaged-app test, close Hermes and temporarily move or delete:

```text
%APPDATA%\Hermes
```

Then launch the app again.

Use this especially when:
- you changed embedding provider/model
- you suspect stale ChromaDB data
- the packaged build behaves differently from a fresh install

---

## Problem: You need logs, but the packaged app does not show enough

Right now the Python backend logs mainly to stdout, which is easy to see when you run `hermes-server.exe` manually for troubleshooting, but not as convenient from the installed GUI app.

So the fastest diagnostic path is:

1. run the sidecar manually:

```powershell
cd src-tauri\target\release
.\hermes-server.exe --port 0 --packaged
```

2. check whether it prints `PORT=...`
3. check whether `/api/health` responds
4. only then go back to testing `app.exe` or the installed app

---

## Minimal release-test checklist

Use this after every `make bundle-app`:

1. Run `src-tauri\target\release\app.exe`
2. Confirm the splash screen disappears and the chat UI opens
3. Open **Settings** and verify the app is responsive
4. Open **Documents** and ingest a small test file
5. Ask one simple chat question
6. Run **one installer** (`setup.exe` or `.msi`)
7. Launch the installed Hermes app from the shortcut / Start Menu
8. Repeat the same smoke test there

If step 2 fails, troubleshoot the sidecar startup before testing anything else.

---

## One-sentence rule

For normal release testing, run **`app.exe`** or the **installed Hermes app** — not `hermes-server.exe`.
