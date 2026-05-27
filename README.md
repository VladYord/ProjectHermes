# Hermes — Local-First AI Knowledge Agent

[![Latest Release](https://img.shields.io/github/v/release/YOUR_USERNAME/ProjectHermes?label=Download&logo=github&color=blue)](https://github.com/YOUR_USERNAME/ProjectHermes/releases/latest)
[![Build](https://img.shields.io/github/actions/workflow/status/YOUR_USERNAME/ProjectHermes/build-release.yml?label=Build)](https://github.com/YOUR_USERNAME/ProjectHermes/actions/workflows/build-release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](#download)

> Chat with your private documents using local or cloud LLMs — your data never leaves your machine.

---

## Screenshot

![Hermes UI](screenshots/HermesScreenshot.png)

---

## Features

- **Privacy-first RAG** — Documents and vector embeddings stay entirely on your machine
- **Multi-format ingestion** — PDF, DOCX, Markdown, code files, plain text, and scanned images (OCR)
- **Pluggable LLM providers** — Ollama (local), OpenAI, and Google Gemini via your own API key
- **Streaming chat** — Token-by-token SSE responses with conversation memory across turns
- **VS Code Copilot integration** — Exposes an MCP server so Copilot can search your knowledge base
- **Native desktop app** — Tauri-powered installer for Windows, macOS, and Linux; no separate server to manage

---

## Download

| Platform | Installer |
|----------|-----------|
| Windows  | [Hermes_x64-setup.exe](https://github.com/YOUR_USERNAME/ProjectHermes/releases/latest) |
| macOS    | [Hermes_x64.dmg](https://github.com/YOUR_USERNAME/ProjectHermes/releases/latest) |
| Linux    | [hermes_amd64.AppImage](https://github.com/YOUR_USERNAME/ProjectHermes/releases/latest) |

> All releases are on the [GitHub Releases page](https://github.com/YOUR_USERNAME/ProjectHermes/releases).

---

## Getting Started

1. **Download and install** the installer for your platform from the table above.
2. **Open Settings** (gear icon) → enter your LLM provider API key, or point Hermes at a local Ollama instance.
3. **Ingest a document** using the Documents panel, then start chatting.

For Ollama (free, fully local):
```bash
# Install Ollama: https://ollama.com/download
ollama pull llama3.1
```
Then in Settings → LLM Provider → select **Ollama** → `http://localhost:11434`.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Hermes Desktop App (Tauri)                     │
│                                                 │
│  ┌─────────────────┐   ┌─────────────────────┐  │
│  │  Svelte 5 UI    │   │  Python Sidecar     │  │
│  │  (WebView)      │◄──│  FastAPI + LangChain│  │
│  │                 │   │  ChromaDB (local)   │  │
│  └─────────────────┘   └─────────────────────┘  │
│           │                      │              │
└───────────┼──────────────────────┼──────────────┘
            │ REST + SSE           │ optional
            ▼                      ▼
     Tauri IPC bridge        Cloud LLM API
                             (user's own key)
```

All document data and vector embeddings are stored locally in your OS app-data directory. The cloud LLM only receives your question and the retrieved text snippets — never the original file.

---

## Development

### Prerequisites

- Python 3.12+, Node.js 20+, Rust stable
- [Ollama](https://ollama.com) (optional — for local LLMs)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (optional — for image ingestion)

### Run in dev mode

```powershell
# Terminal 1 — Python backend
.venv\Scripts\python.exe -m hermes --port 8000

# Terminal 2 — Tauri dev window (starts Vite HMR automatically)
make dev
```

`make dev` creates a dev stub binary (so Tauri compiles), then launches `cargo tauri dev`.  
The Svelte frontend connects to the running Python backend at `http://127.0.0.1:8000`.

### Run tests

```powershell
make test        # pytest (76 tests)
cd ui && npm run check   # svelte-check + tsc (0 errors)
```

### Production build

```powershell
make bundle-app  # PyInstaller + cargo tauri build → platform installer
```

---

## VS Code Copilot (MCP)

Hermes exposes an MCP server so GitHub Copilot can search your knowledge base directly.

Add to VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "hermes": {
        "command": "C:\\path\\to\\project\\.venv\\Scripts\\python.exe",
        "args": ["-m", "hermes", "--mcp"]
      }
    }
  }
}
```

Available tools: `search_knowledge`, `ask_hermes`, `ingest_document`, `list_documents`, `remove_document`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop shell | [Tauri 2](https://tauri.app) (Rust) |
| Frontend | [Svelte 5](https://svelte.dev) + TypeScript + Vite |
| Backend | [FastAPI](https://fastapi.tiangolo.com) + [uvicorn](https://www.uvicorn.org) |
| AI / Agent | [LangChain](https://langchain.com) |
| Vector store | [ChromaDB](https://www.trychroma.com) (local, persistent) |
| LLM providers | Ollama · OpenAI · Google Gemini |
| Document parsing | PyMuPDF · python-docx · Tesseract OCR |
| Packaging | PyInstaller + Tauri bundler |
| CI/CD | GitHub Actions (Windows · macOS · Linux) |

---

## License

MIT — see [LICENSE](LICENSE).
