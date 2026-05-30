# Hermes Desktop App — Implementation Plan Overview

**Status Legend:** 🔴 Not Started | 🟡 In Progress | 🟢 Done | ⏸ Blocked

| Phase | Title | Status | Summary Doc |
|---|---|---|---|
| 0 | Monorepo Setup & Tauri Scaffold | � Done | [Phase0_Scaffold.md](Phase0_Scaffold.md) |
| 1 | Backend Hardening | � Done | [Phase1_Backend.md](Phase1_Backend.md) |
| 2 | Svelte Frontend — Chat UI | � Done | [Phase2_ChatUI.md](Phase2_ChatUI.md) |
| 3 | Svelte Frontend — Document Manager | � Done | [Phase3_DocManager.md](Phase3_DocManager.md) |
| 4 | Svelte Frontend — Settings | � Done | [Phase4_Settings.md](Phase4_Settings.md) |
| 5 | Tauri Integration | � Done | [Phase5_TauriIntegration.md](Phase5_TauriIntegration.md) |
| 6 | PyInstaller & Tauri Build Pipeline | � Done | [Phase6_BuildPipeline.md](Phase6_BuildPipeline.md) |
| 7 | GitHub Actions CI/CD | 🔴 Not Started | [Phase7_CICD.md](Phase7_CICD.md) |
| 8 | GitHub Pages Landing | 🔴 Not Started | [Phase8_Pages.md](Phase8_Pages.md) |

---

## Architecture Summary

```
┌──────────────────────────── Tauri 2.11.2 Window ─────────────────────────────┐
│  Svelte 5.55.9 WebView  (tauri://localhost)                                   │
│  ┌─────────────┐  ┌──────────────────────┐  ┌────────────────────────────┐  │
│  │ ChatSidebar │  │     ChatWindow        │  │  DocManager  |  Settings   │  │
│  └─────────────┘  └──────────────────────┘  └────────────────────────────┘  │
│                       HTTP localhost:DYNAMIC_PORT                              │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
          ┌────────────────────────────▼──────────────────────────────┐
          │    Python FastAPI Sidecar  (hermes-server-{target}.exe)   │
          │                                                            │
          │  ┌────────────────────────────────────────────────────┐  │
          │  │  REST API + SSE Streaming  |  MCP Server           │  │
          │  └────────────────────────────────────────────────────┘  │
          │  ┌─────────────────┐ ┌─────────────────┐ ┌───────────┐  │
          │  │ ChromaDB 1.5.9  │ │ SQLite Sessions │ │config.enc │  │
          │  │ (APP_DATA/...)  │ │  (aiosqlite)    │ │ AES-256   │  │
          │  └─────────────────┘ └─────────────────┘ └───────────┘  │
          └────────────────────────────────────────────────────────────┘
                    │                              │
              Ollama (auto-detect)       OpenAI / Gemini APIs
```

---

## Repository Layout (Target State)

```
ProjectHermes/
├── hermes/                    # Python backend (existing + modified)
│   ├── config_manager.py      # NEW — encrypted config, app-data paths
│   └── ... (existing files)
├── ui/                        # NEW — Svelte 5.55.9 + Vite frontend
│   ├── src/
│   │   ├── app.html
│   │   ├── App.svelte
│   │   └── lib/
│   │       ├── api/           # TypeScript API client (REST + SSE)
│   │       ├── components/    # Svelte UI components
│   │       └── stores/        # Svelte 5 rune-based state
│   ├── package.json
│   └── vite.config.ts
├── src-tauri/                 # NEW — Tauri 2.11.2 Rust shell
│   ├── src/main.rs
│   ├── Cargo.toml
│   ├── build.rs
│   └── tauri.conf.json
├── packaging/                 # NEW — all build/release artifacts
│   ├── pyinstaller/
│   │   └── hermes.spec        # PyInstaller build specification
│   ├── scripts/
│   │   ├── build-backend.ps1  # Windows build script
│   │   └── build-backend.sh   # Unix build script
│   └── tesseract/             # Populated by CI (platform binaries)
├── docs-site/                 # NEW — GitHub Pages static site
│   ├── index.html
│   └── style.css
├── doc/
│   ├── plan/                  # NEW — this folder (phase plan docs)
│   └── (existing docs)
├── .github/
│   └── workflows/
│       ├── build-release.yml  # NEW — multi-platform release
│       └── pages.yml          # NEW — GitHub Pages deploy
└── Makefile                   # Extended with new targets
```

---

## Key Technology Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Desktop framework | Tauri 2.11.2 | Lightweight vs Electron, Rust security model |
| Frontend | Svelte 5.55.9 + Vite | Minimal bundle, rune reactivity, fast HMR |
| Python packaging | PyInstaller sidecar | Preserves entire Python/LangChain ecosystem |
| Port negotiation | stdout `PORT=XXXX` | Clean IPC, no file-race conditions |
| API key storage | AES-256-GCM encrypted file | Cross-platform, no keychain dependency |
| Session persistence | SQLite + aiosqlite | Zero extra infrastructure, async, embeddable |
| ChromaDB | Embedded persistent (1.5.9) | Bundled in PyInstaller, no separate server |
| OCR | Tesseract bundled | Works out of box for image ingestion |
| Ollama | Detect + guide | Cannot silently bundle (system service) |
| Auto-update | Manual (GitHub Releases) | Simpler, user controls updates |
| Target platforms | Windows x64, macOS, Linux x64 | Covers 99%+ of developer/knowledge-worker PCs |

---

## Manual Prerequisites (do once before Phase 0)

> These are **one-time human actions** that cannot be automated. Complete them before running any implementation commands.

### 🛠 MANUAL STEP 1 — Install Node.js ≥20 LTS
- Download from https://nodejs.org/en/download (pick **LTS** → Windows Installer)
- Verify: `node --version` prints `v20.x.x` or higher

### 🛠 MANUAL STEP 2 — Install Rust toolchain
- Run in PowerShell: `winget install Rustlang.Rust.MSVC` — or go to https://rustup.rs and run the installer
- Select **default installation** when prompted
- Restart your terminal after install
- Verify: `rustc --version` and `cargo --version` both print a version

### 🛠 MANUAL STEP 3 — Install Tauri CLI
```powershell
cargo install tauri-cli --version "^2"
```
- This takes 5-10 minutes (compiles from source)
- Verify: `cargo tauri --version` prints `tauri-cli 2.x.x`

### 🛠 MANUAL STEP 4 — Enable Windows Developer Mode (Windows only)
- Required for Tauri to create symlinks during build
- Go to: **Settings → System → For developers → Developer Mode → On**
- Without this, `cargo tauri build` will fail with a symlink permission error

### 🛠 MANUAL STEP 5 — Create a public GitHub repository
- Go to https://github.com/new
- Name: `ProjectHermes` (or your preferred name)
- Visibility: **Public** (required for free GitHub Pages + portfolio)
- Initialize with a README: **yes**
- Add `.gitignore`: Python
- After creation: push this local project to that repo
```powershell
git remote add origin https://github.com/YOUR_USERNAME/ProjectHermes.git
git push -u origin main
```

### 🛠 MANUAL STEP 6 — Configure GitHub Actions permissions
- In your GitHub repo → **Settings → Actions → General → Workflow permissions**
- Select **Read and write permissions** → Save
- This allows the release workflow to create GitHub Releases automatically

### 🛠 MANUAL STEP 7 — (Optional) Enable GitHub Pages
- Only needed if you want Phase 8 (landing site). Skip if not doing Phase 8.
- In your GitHub repo → **Settings → Pages → Source → GitHub Actions** → Save

---

## Verified Library Versions (May 2026)

| Package | Version | Source |
|---|---|---|
| tauri (Rust crate) | 2.11.2 | github.com/tauri-apps/tauri |
| tauri-cli | 2.11.2 | github.com/tauri-apps/tauri |
| @tauri-apps/api | ^2.x | npm |
| svelte | 5.55.9 | github.com/sveltejs/svelte |
| vite | ^6.x | npm |
| chromadb (Python) | 1.5.9 | pypi.org |
| Python | ≥3.12 | existing requirement |
| cryptography | ≥44.x | pypi.org |
| aiosqlite | ≥0.21.x | pypi.org |
| litellm | ≥1.0 | pypi.org |
| langchain-litellm | ≥0.2 | pypi.org |

---

## Execution Instructions

> **Each phase has its own plan document linked above.**
> To start a phase, say: `"implement Phase N"` or `"start Phase N"`.
> The plan document for that phase will be used as context for implementation.
> After completing a phase, update its Status field to 🟢 Done before starting the next.

### Phase Dependency Graph

```
Phase 0 (scaffold)
    └─► Phase 1 (backend hardening)
            └─► Phase 2 (chat UI)
                    └─► Phase 3 (doc manager)
                            └─► Phase 4 (settings UI)
                                    └─► Phase 5 (Tauri integration)
                                            └─► Phase 6 (build pipeline)
                                                    └─► Phase 7 (CI/CD + README)
                                                            └─► Phase 8 (GitHub Pages — OPTIONAL)
```

Phases 0–7 are sequential. **Phase 8 is optional** — skip it if you only need the portfolio repo + download releases.

---

## Open Questions / Future Enhancements

- [ ] Code signing certificates: required for Windows SmartScreen bypass and macOS Gatekeeper. Document how to add signing in Phase 7 notes.
- [ ] Session export: allow user to export chat history as markdown or JSON.
- [ ] Document summary generation: auto-generate a 2-3 sentence summary of each ingested doc using the LLM.
- [ ] Embedding model auto-detection: warn user when switching providers if ChromaDB dimension will change (LL-01 from LessonsLearned.md).
- [ ] Drag-and-drop ingestion: drop files directly onto the app window.
- [ ] App icon / branding: placeholder icon used until brand assets provided.
