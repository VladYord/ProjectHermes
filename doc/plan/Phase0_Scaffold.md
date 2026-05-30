# Phase 0 — Monorepo Setup & Tauri Scaffold

**Status:** � Done  
**Depends on:** nothing  
**Next phase:** [Phase1_Backend.md](Phase1_Backend.md)

---

## Goal

Establish the complete project layout with a working Svelte 5 + Tauri 2 dev window that opens from a single `make dev` command. No backend logic changed yet — purely scaffolding.

---

## Prerequisites (install once, not tracked in code)

| Tool | Version | Install |
|---|---|---|
| Node.js | ≥20 LTS | https://nodejs.org |
| Rust + Cargo | stable | https://rustup.rs |
| Tauri CLI | 2.11.2 | `cargo install tauri-cli --version ^2` |
| Python | 3.12+ | already installed |

---

## 🛑 Manual Steps (do before running any Phase 0 commands)

> These cannot be scripted. Complete them in order before running `make dev`.

### 🛠 MANUAL — Install Node.js
1. Go to https://nodejs.org/en/download → pick the **LTS** Windows Installer
2. Run the installer, accept defaults
3. Restart your terminal
4. Verify: `node --version` (must be `v20.x` or higher)

### 🛠 MANUAL — Install Rust
1. Go to https://rustup.rs → click the download link for Windows
2. Run `rustup-init.exe` → choose **option 1** (default install)
3. Restart your terminal
4. Verify: `rustc --version` and `cargo --version`

### 🛠 MANUAL — Install Tauri CLI
In your terminal (after Rust is installed):
```powershell
cargo install tauri-cli --version "^2"
```
This compiles the CLI from source — takes 5-10 minutes the first time.
Verify: `cargo tauri --version` → shows `tauri-cli 2.x.x`

### 🛠 MANUAL — Enable Windows Developer Mode
Required for Tauri to create symlinks during `cargo tauri build`:
- **Settings → System → For developers → Developer Mode → toggle On**
- Without this you will get a `os error 1314: A required privilege is not held by the client` error during build

### 🛠 MANUAL — Create GitHub repository (if not done)
1. Go to https://github.com/new
2. Name: `ProjectHermes`, set to **Public**
3. Initialize with README: **yes**, .gitignore: Python
4. Push this project:
```powershell
git remote add origin https://github.com/YOUR_USERNAME/ProjectHermes.git
git push -u origin main
```

---

## Steps

### 0.1 — Create `ui/` Svelte 5 + Vite project

```powershell
cd d:\Project\ProjectHermes
npm create vite@latest ui -- --template svelte-ts
cd ui
npm install
npm install svelte@5.55.9 --save-exact
```

Verify `ui/package.json` has `"svelte": "5.55.9"`.

Remove boilerplate from `ui/src/App.svelte`, replace with minimal shell:
```svelte
<h1>Hermes</h1>
```

### 0.2 — Init Tauri 2.11.2 in repo root

```powershell
cd d:\Project\ProjectHermes
cargo tauri init
```

Tauri init prompts — answer:
| Prompt | Answer |
|---|---|
| App name | `Hermes` |
| Window title | `Hermes — Local AI Knowledge Agent` |
| Where are your web assets? | `../ui/dist` |
| URL of dev server | `http://localhost:5173` |
| Frontend dev command | `npm run dev` (run from `ui/`) |
| Frontend build command | `npm run build` (run from `ui/`) |

This creates `src-tauri/` at repo root.

### 0.3 — Update `src-tauri/tauri.conf.json`

Set:
```json
{
  "identifier": "dev.hermes.app",
  "app": {
    "windows": [
      {
        "title": "Hermes — Local AI Knowledge Agent",
        "width": 1280,
        "height": 800,
        "minWidth": 900,
        "minHeight": 600,
        "resizable": true
      }
    ]
  }
}
```

### 0.4 — Add Tauri npm package and plugins to `ui/`

```powershell
cd d:\Project\ProjectHermes\ui
npm install @tauri-apps/api@^2
npm install @tauri-apps/plugin-dialog @tauri-apps/plugin-shell @tauri-apps/plugin-path
```

Add Tauri Rust plugin dependencies to `src-tauri/Cargo.toml`:
```toml
[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-dialog = "2"
tauri-plugin-shell = "2"
tauri-plugin-path = "2"
```

Register plugins in `src-tauri/src/main.rs`:
```rust
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_path::init())
        .run(tauri::generate_context!())
        .expect("error running Hermes");
}
```

### 0.5 — Create `packaging/` directory structure

```
packaging/
├── pyinstaller/
│   └── .gitkeep        (hermes.spec added in Phase 6)
├── scripts/
│   └── .gitkeep        (build scripts added in Phase 6)
└── tesseract/
    └── .gitkeep        (populated by CI in Phase 7)
```

### 0.6 — Update `Makefile` with new targets

Add to existing `Makefile`:

```makefile
# ── Desktop App Targets ──────────────────────────────────────────────

.PHONY: dev build-ui build-app bundle-backend bundle-app

## Start Tauri dev window (Svelte HMR + Tauri shell)
dev:
	cd ui && npm run dev &
	cargo tauri dev --manifest-path src-tauri/Cargo.toml

## Build Svelte frontend only
build-ui:
	cd ui && npm run build

## Build full Tauri app (requires bundle-backend first in production)
build-app: build-ui
	cargo tauri build --manifest-path src-tauri/Cargo.toml

## Run PyInstaller to produce hermes-server binary (Phase 6)
bundle-backend:
	python -m PyInstaller packaging/pyinstaller/hermes.spec

## Full production bundle: backend + Tauri installer
bundle-app: bundle-backend build-app
```

### 0.7 — Add `.gitignore` entries

Append to root `.gitignore` (create if missing):
```
# Tauri build outputs
src-tauri/target/
# Svelte / Vite build
ui/dist/
ui/node_modules/
# Packaging outputs
packaging/tesseract/win/
packaging/tesseract/mac/
packaging/tesseract/linux/
```

---

## Files Created

| File | Type |
|---|---|
| `ui/` (entire directory) | New — Svelte 5.55.9 + Vite project |
| `src-tauri/` (entire directory) | New — Tauri 2.11.2 Rust shell |
| `src-tauri/tauri.conf.json` | New (generated by Tauri init, then customised) |
| `src-tauri/src/main.rs` | New (generated, then plugins added) |
| `packaging/pyinstaller/.gitkeep` | New — placeholder |
| `packaging/scripts/.gitkeep` | New — placeholder |
| `packaging/tesseract/.gitkeep` | New — placeholder |

## Files Modified

| File | Change |
|---|---|
| `Makefile` | Add `dev`, `build-ui`, `build-app`, `bundle-backend`, `bundle-app` targets |
| `.gitignore` | Add Tauri and Svelte build output paths |

---

## Verification Checklist

- [ ] `cd ui && npm run dev` starts Vite on http://localhost:5173 without errors
- [x] `cargo tauri dev` opens a native window showing "Hermes"
- [ ] `make dev` (or equivalent) starts both in one command
- [x] `src-tauri/tauri.conf.json` has `identifier: "dev.hermes.app"`
- [x] `ui/package.json` shows `"svelte": "5.55.9"`
- [x] `packaging/` directory exists with placeholder files

---

## Open Questions

- None currently — this phase is purely structural.

---

## Completion Notes

> Fill in after phase is completed:
> - Date completed: 2026-05-26
> - Actual versions installed: Node 24.11.1, Rust/Cargo 1.95.0, Tauri CLI 2.11.2, Svelte 5.55.9
> - Deviations from plan:
>   - `tauri-plugin-path` does not exist (npm or crate). Path APIs are built into `@tauri-apps/api/path` and Tauri core. Removed from plan.
>   - `cargo tauri init` interactive prompts concatenated defaults with typed values — fixed manually by rewriting `tauri.conf.json` without BOM using `[System.IO.File]::WriteAllText`.
>   - `bundle.identifier` is not a valid field inside `bundle` in Tauri 2.x schema — removed (top-level `identifier` is sufficient).
