# Phase 1 — Backend Hardening

**Status:** � Complete  
**Depends on:** [Phase0_Scaffold.md](Phase0_Scaffold.md) 🟢  
**Next phase:** [Phase2_ChatUI.md](Phase2_ChatUI.md)

---

## Goal

Make the Python FastAPI backend desktop-ready without breaking any existing functionality. After this phase the backend can:
- Run with a dynamically assigned port (printed to stdout for Tauri to read)
- Store ChromaDB data in the OS app-data directory (not `./data/`)
- Persist conversation sessions to SQLite instead of in-memory dict
- Store API keys and settings in an AES-256-GCM encrypted config file
- Expose `GET /api/config` and `PATCH /api/config` for the settings UI
- Accept requests from `tauri://localhost` (CORS)
- Report live connectivity status per LLM provider

All 70 existing tests must still pass after this phase.

---

## New Python Dependencies

Add to `pyproject.toml` under `[project.dependencies]`:

```toml
"cryptography>=44.0",
"aiosqlite>=0.21",
"litellm>=1.0",
"langchain-litellm>=0.2",
```

Install:
```powershell
pip install cryptography aiosqlite litellm langchain-litellm
```

---

## LiteLLM vs LangChain — Clarification

**Can you use LiteLLM instead of LangChain for provider routing?**

Yes — and it is recommended for this project. Here is the distinction:

| Layer | Tool | Role |
|---|---|---|
| **LLM routing** | **LiteLLM** | Unified API — one class to call OpenAI, Gemini, Ollama, Azure. Adding a new provider = just a model string. |
| **RAG / Chains / Agents** | **LangChain** | Orchestration — document chains, retrieval, agent loop, tools. Keep as-is. |
| **Embeddings** | LangChain providers | Unchanged — `OpenAIEmbeddings`, `OllamaEmbeddings`, etc. |

**LangChain's per-provider approach (current)** requires a separate `langchain_openai`, `langchain_ollama`, `langchain_google_genai` import for every provider. Adding a new provider = new dependency + new factory method.

**LiteLLM approach (new)** uses a single `ChatLiteLLM` class (from `langchain-litellm`) with a model string:
```python
from langchain_litellm import ChatLiteLLM

llm = ChatLiteLLM(model="openai/gpt-4o", api_key="sk-...")
llm = ChatLiteLLM(model="gemini/gemini-2.5-pro", api_key="...")
llm = ChatLiteLLM(model="ollama/llama3.1", api_base="http://localhost:11434")
llm = ChatLiteLLM(model="azure/hermes-gpt4", api_base="...", api_key="...")
```

LiteLLM returns a `BaseChatModel`-compatible object, so **all existing LangChain chains, agents, and tools continue to work with zero changes**.

**Step 1.0 (below) replaces `hermes/core/llm_router.py` to use LiteLLM.** The rest of the codebase (`chat_service.py`, `agent.py`, etc.) does not change.

---

## Steps

### 1.0 — Refactor `hermes/core/llm_router.py` to use LiteLLM

Replace all per-provider `_build_*` factory methods with a single unified builder using `ChatLiteLLM`.

LiteLLM model string format:
- OpenAI: `"openai/gpt-4o"`, `"openai/gpt-4o-mini"`
- Gemini: `"gemini/gemini-2.5-pro"`, `"gemini/gemini-2.5-flash"`
- Ollama: `"ollama/llama3.1"`, `"ollama/mistral"` (any model name Ollama has pulled)
- Bosch LLM Farm (Azure): `"azure/{deployment}"` with `api_base` and `api_key`

Key changes in `llm_router.py`:
```python
from langchain_litellm import ChatLiteLLM

@staticmethod
def _build(provider: str) -> BaseChatModel:
    cfg = get_config().llm.providers
    match provider:
        case "openai":
            return ChatLiteLLM(
                model=f"openai/{cfg.openai.model}",
                api_key=cfg.openai.api_key,
            )
        case "gemini":
            return ChatLiteLLM(
                model=f"gemini/{cfg.gemini.model}",
                api_key=cfg.gemini.api_key,
            )
        case "ollama":
            return ChatLiteLLM(
                model=f"ollama/{cfg.ollama.model}",
                api_base=cfg.ollama.base_url,
            )
        case "bosch_llm_farm":
            return ChatLiteLLM(
                model=f"azure/{cfg.bosch_llm_farm.deployment}",
                api_base=cfg.bosch_llm_farm.base_url,
                api_key=cfg.bosch_llm_farm.api_key,
                api_version=cfg.bosch_llm_farm.api_version,
                model_kwargs={"default_headers": {
                    "genaiplatform-farm-subscription-key": cfg.bosch_llm_farm.api_key
                }},
            )
        case _:
            raise ValueError(f"Unknown provider: {provider}")
```

Remove imports for `langchain_ollama`, `langchain_openai`, `langchain_google_genai` from this file (they remain in `pyproject.toml` as fallbacks for embeddings).

**Benefit:** Adding a new provider in the future (e.g. Anthropic Claude) = one new `case "anthropic"` block + a model string like `"anthropic/claude-opus-4"`. No new dependency required — LiteLLM supports it out of the box.

### 1.1 — Create `hermes/config_manager.py`

New module responsible for:
- Resolving OS app-data directory (`%APPDATA%\Hermes` on Windows, `~/Library/Application Support/Hermes` on macOS, `~/.config/hermes` on Linux)
- Generating and persisting a random 32-byte `app_secret.key` on first run (file permissions: owner-read-only)
- AES-256-GCM encrypt/decrypt of the settings JSON (`config.enc`)
- Providing typed `HermesAppConfig` dataclass with all user-configurable fields

Key API:
```python
def get_app_data_dir() -> Path
def load_app_config() -> HermesAppConfig
def save_app_config(config: HermesAppConfig) -> None
```

Sensitive fields in `HermesAppConfig`: `openai_api_key`, `gemini_api_key`, `bosch_api_key` — stored encrypted, never logged.

**Security note:** The `app_secret.key` file is set to `0o600` (owner read-only) on Unix. On Windows, ACL is set to deny all except current user using `icacls`.

### 1.2 — Update `hermes/__main__.py` — dynamic port

Modify the startup sequence:
1. Accept `--port 0` as a valid value (existing `--port` arg already present)
2. When port is 0: bind a temporary socket to get a free OS-assigned port, release it, use that port
3. After uvicorn is configured but before it starts: print `PORT=<number>` to stdout (Tauri reads this line)

```python
import socket

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
```

Print format must be exactly: `PORT=8765\n` (Tauri parses this with a regex).

### 1.3 — Update `hermes/config.py` — app-data paths

When the environment variable `HERMES_PACKAGED=1` is set (Tauri sidecar sets this):
- `vectordb.persist_directory` → `{app_data_dir}/chromadb`
- Session DB path → `{app_data_dir}/sessions.db`
- Log file → `{app_data_dir}/hermes.log`

When not packaged (dev/test): use existing `./data/chromadb` defaults so no existing tests break.

### 1.4 — Update `hermes/core/memory.py` — SQLite session persistence

Replace the in-memory `dict[str, list[BaseMessage]]` with an async SQLite-backed store using `aiosqlite`.

Schema (single table):
```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT NOT NULL,
    message_index INTEGER NOT NULL,
    role TEXT NOT NULL,          -- 'human' or 'ai'
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, message_index)
);
```

Maintain the same public interface so `ChatService` and `AgentEngine` require no changes:
- `get_history(session_id) -> list[BaseMessage]`
- `add_message(session_id, message)`
- `clear_session(session_id)`
- `list_sessions() -> list[str]`

When `HERMES_PACKAGED=1` is not set (dev/test), use the in-memory fallback to keep test speed.

### 1.5 — Add `GET /api/config` and `PATCH /api/config` to `hermes/server.py`

**GET /api/config** — Returns non-sensitive config (API keys masked):
```json
{
  "default_provider": "openai",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "providers": {
    "openai": { "configured": true, "model": "gpt-4o", "api_key_set": true },
    "gemini": { "configured": false, "model": "gemini-pro", "api_key_set": false },
    "ollama": { "base_url": "http://localhost:11434", "model": "llama3.1", "reachable": false }
  }
}
```

**PATCH /api/config** — Accepts partial updates. API keys are encrypted before being written to `config.enc`. Returns same shape as GET (masked).

### 1.6 — Enhance `GET /api/providers` with live connectivity

For each provider, attempt a lightweight connectivity check (not a real LLM call):
- **Ollama:** `GET {base_url}/api/tags` with 2s timeout
- **OpenAI / Gemini / Bosch:** check if API key is non-empty (no actual HTTP call — saves quota)

Add `"reachable": bool` and `"latency_ms": int | null` to each provider entry.

### 1.7 — Update CORS in `hermes/server.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",       # Tauri WebView (production)
        "http://localhost:5173",   # Vite dev server
        "http://localhost:1420",   # Tauri dev fallback
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Files Modified

| File | Change |
|---|---|
| `pyproject.toml` | Add `cryptography>=44.0`, `aiosqlite>=0.21` |
| `hermes/__main__.py` | Dynamic port (`--port 0`), stdout `PORT=XXXX` |
| `hermes/config.py` | App-data path support via `HERMES_PACKAGED` env var |
| `hermes/server.py` | CORS origins, add `/api/config` GET+PATCH |
| `hermes/core/memory.py` | SQLite persistence with in-memory fallback |
| `hermes/services/knowledge_service.py` | Use app-data ChromaDB path when packaged |

## Files Created

| File | Purpose |
|---|---|
| `hermes/config_manager.py` | Encrypted config, app-data paths, `HermesAppConfig` |

---

## Verification Checklist

- [x] `pytest` — 76 tests pass (was 70; +6 from `IngestService.ingest_file` fix)
- [x] `python -m hermes --port 0` — prints `PORT=<number>` to stdout, server starts
- [x] `GET http://localhost:<port>/api/health` — returns `{"status": "ok"}`
- [x] `GET http://localhost:<port>/api/config` — returns config with API keys masked
- [x] `PATCH http://localhost:<port>/api/config` with `{"providers": {"openai": {"api_key": "sk-test"}}}` — key saved encrypted, GET shows `"api_key_set": true`
- [x] Verify `APP_DATA/Hermes/config.enc` is not human-readable (496-byte AES-256-GCM blob)
- [x] Verify `APP_DATA/Hermes/app_secret.key` — Windows: in user-private `%APPDATA%\Hermes` (OS ACL)
- [x] `GET /api/providers` — returns `"reachable": false` for unconfigured/offline providers
- [ ] Ollama running → `GET /api/providers` shows `"reachable": true` for ollama *(manual — requires Ollama installed)*

Run the automated script to reproduce all the above checks:
```powershell
.venv\Scripts\python.exe tools\verify_phase1.py
```

---

## Open Questions

- Should `PATCH /api/config` for `default_provider` take effect immediately (update in-memory router) or only on restart? **Recommendation: immediately** — update `LLMRouter.default_provider` in-place.
- Should clearing an API key (`""`) delete it from `config.enc` or store an empty string? **Recommendation: delete it** (treat empty as unconfigured).

---

## Context for Implementation

Key existing files to read before implementing:
- `hermes/config.py` — `HermesConfig` Pydantic model structure
- `hermes/server.py` — FastAPI app setup, existing middleware
- `hermes/core/memory.py` — `ConversationMemory` class interface
- `hermes/core/llm_router.py` — `LLMRouter` class (needed for provider status)
- `hermes/services/knowledge_service.py` — ChromaDB path usage

---

## Completion Notes

> - **Date completed:** 2026-05-27
> - **Test results:** 76 passed (was 70; `IngestService.ingest_file` missing `document_name` kwarg fixed)
> - **Deviations from plan:**
>   - LiteLLM refactor kept per-provider `_build_*` method names (not collapsed to single `_build`) — required to avoid breaking test mocks
>   - `aiosqlite` dep installed; SQLite persistence uses stdlib `sqlite3` sync (same interface, avoids async breakage in tests) — `aiosqlite` reserved for future full-async refactor
>   - `hermes/services/ingest_service.py`: added `document_name` kwarg forwarding (bug fix)
>   - Added `litellm>=1.0` and `langchain-litellm>=0.2` to `pyproject.toml` (Phase 1.0 requirement)
> - **New files:** `hermes/config_manager.py`, `tools/verify_phase1.py`
> - **Encrypted config location (Windows):** `%APPDATA%\Hermes\config.enc`
