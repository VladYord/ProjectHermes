# Project Hermes — RAG, Desktop AI & Agent Learning Path

> **Audience:** Python developer building a RAG application, desktop AI app, REST backend, or MCP server  
> **Assumes:** Python proficiency  
> **Tied to:** Project Hermes codebase — every concept maps to a real file  
> **Current stack:** Tauri + Svelte + FastAPI sidecar  
> **Date:** 2026-05-29

---

## How to Use This Guide

1. Follow phases **in order** — each phase builds on the previous one
2. For each phase, **build a small script first** before reading the Hermes source file
3. Every "Study in Hermes" link points to the exact file where that concept lives
4. Skipping ahead is possible only for Phase 6–7; all others have hard dependencies

---

## Current Implementation Snapshot

`Vision.md` still describes the core Hermes goal correctly: a privacy-first assistant for talking to your own documents. What changed is the delivery model. The original MVP idea assumed a browser-style frontend, but the implemented product described in `doc/plan` is now a desktop app built from:

- **Tauri** as the desktop shell
- **Svelte 5** as the frontend UI
- **Python FastAPI** as the backend sidecar
- **ChromaDB** for local vector storage
- **SQLite** for chat/session persistence
- **Encrypted app config** for provider settings and API keys

### Vision vs. Current Product

| Area | Original Vision | Current Implementation |
|---|---|---|
| Frontend | Next.js browser app | Svelte app inside a Tauri window |
| Runtime | Frontend and backend started separately | Tauri starts the Python sidecar and passes the chosen port to the UI |
| Backend | FastAPI + LangChain + ChromaDB | Still FastAPI + LangChain + ChromaDB, now with session persistence and MCP support |
| Packaging | Developer-run local stack | PyInstaller sidecar bundled into Tauri installers |
| UX scope | Simple chat with one ingested document | Desktop workspace with chat, document manager, settings, provider switching, and native file dialogs |

### Plan Status That Matters

Phases **0 through 6** in `doc/plan/Plan_Overview.md` are implemented. That means:

- the desktop shell exists
- the Svelte chat UI exists
- the document manager and settings panels exist
- Tauri sidecar startup and shutdown are wired
- the PyInstaller/Tauri packaging pipeline is working

Phases 7 and 8 are still future work, so CI/CD and the public landing-site automation are not yet part of the shipped product.

### Important Build-Pipeline Update

The backend executable is no longer built directly into `src-tauri/resources`.

The current pipeline is:

```text
PyInstaller -> backend/dist/hermes-server-<target>.exe
                    -> copy step
                    -> src-tauri/resources/hermes-server-<target>.exe
                    -> cargo tauri build
```

This separation avoids Windows file-locking failures during bundling.

---

## How Hermes Can Be Used

Hermes is useful beyond being a study project for RAG internals.

- **Personal knowledge assistant** — ingest PDFs, markdown notes, text files, code files, DOCX documents, and OCR-readable images, then ask questions across them
- **Engineering reference tool** — keep specifications, manuals, code snippets, and operational docs in one local searchable workspace
- **Provider comparison workspace** — switch between Ollama, OpenAI, Gemini, and Azure OpenAI from the same settings surface
- **Privacy-first desktop AI app** — run with Ollama for mostly local question answering over private documents
- **Reusable backend for editors and assistants** — expose the same knowledge and chat services through MCP for tools like VS Code

---

## What Tauri Is and What It Does in Hermes

Tauri is a desktop application framework that uses a native Rust shell plus the operating system WebView to host a web frontend.

In Hermes, Tauri is not the RAG or model layer. It is the desktop runtime that:

- launches the Svelte UI in a native app window
- spawns the packaged Python backend sidecar
- receives the backend handshake `PORT=<number>` from stdout
- exposes that port to the frontend with `get_backend_port` and the `backend-ready` event
- provides desktop-native features like the file picker
- kills the backend process when the user exits the app
- bundles everything into installable desktop artifacts

### Runtime Flow

```text
Tauri launch
    -> spawn hermes-server --port 0 --packaged
    -> wait for stdout: PORT=12345
    -> emit backend-ready { port: 12345 }
    -> Svelte uses http://127.0.0.1:12345/api/...
    -> on app exit, Tauri kills the sidecar
```

---

## Which Svelte UI Calls Which Hermes API

The current app is easiest to understand if you follow the flow:

`component -> store -> api wrapper -> FastAPI endpoint`

| UI surface | Frontend path | API / bridge used | User action |
|---|---|---|---|
| `App.svelte` startup splash | `initBackend()` in `ui/src/lib/backend.svelte.ts` | Tauri `invoke('get_backend_port')`, Tauri `backend-ready`, then `GET /api/health` | Open the app and wait for the backend sidecar |
| `ChatWindow.svelte` | `chatStore.sendMessage()` -> `streamChat()` | `POST /api/chat` with `stream: true` over SSE | Send a chat message and receive streaming tokens |
| `ChatSidebar.svelte` | `loadSessions()`, `setActiveSession()`, `deleteSession()` | `GET /api/sessions`, `GET /api/sessions/{id}/history`, `DELETE /api/sessions/{id}` | Browse, reopen, or delete chat sessions |
| `DocumentManager.svelte` | `docStore.refreshDocuments()` | `GET /api/documents` | Open the knowledge-base panel and list documents |
| `UploadButton.svelte` in packaged mode | Tauri dialog -> `docStore.ingestByPath()` | Tauri dialog plugin + `POST /api/ingest` | Pick local files from the desktop app |
| `UploadButton.svelte` in dev/browser mode | file input -> `docStore.uploadAndIngest()` | `POST /api/ingest/upload` | Upload file bytes directly to the backend |
| `DocumentCard.svelte` | `docStore.removeDocument()` | `DELETE /api/documents/{document_id}` | Remove an ingested document |
| `SettingsPanel.svelte` | `configStore.load()`, `refreshProviders()`, `fetchBackendVersion()` | `GET /api/config`, `GET /api/providers`, `GET /api/health` | Open settings and inspect current provider/backend state |
| `ProviderCard.svelte` | `saveProvider()`, `setDefaultProvider()`, `testProviderChat()` | `PATCH /api/config`, non-streaming `POST /api/chat` | Save provider settings and test chat connectivity |
| `EmbeddingConfig.svelte` | `setEmbeddingProvider()` and provider-specific saves | `PATCH /api/config` | Change embedding provider/model |

### Recommended Reading Order for Features

If you want to understand a user-facing behavior, start from the UI and move inward:

1. Svelte component
2. store in `ui/src/lib/stores`
3. wrapper in `ui/src/lib/api`
4. endpoint in `hermes/server.py`
5. service implementation in `hermes/services`

That reading order mirrors how the application is structured.

---

## Phase 1 — Why RAG Exists (2–3 days)

*Without this foundation, all tools below are just magic boxes.*

### 1.1 How LLMs Work (Concepts Only)

- **Tokens and context windows** — a model cannot read your entire hard drive; it has a fixed context limit (4K–200K tokens depending on model). This is why we need RAG at all.
- **Hallucination** — when an LLM confidently states a wrong fact. This is structural: the model generates the statistically likely next token, not a verified fact. RAG fixes this by providing verified context.
- **Message structure** — every LLM call is a list of messages: System → Human → Assistant → Human → ... This is exactly what `HumanMessage`, `AIMessage`, `SystemMessage` in `hermes/core/agent.py` represents.
- **Temperature / top-p** — temperature = 0 gives deterministic output (good for factual RAG answers); temperature = 1 gives creative variation.

### 1.2 What an Embedding Is

- A sentence, word, or document converted to a list of floats (e.g., 384 numbers)
- Semantically similar texts produce numerically similar vectors
- Similarity is measured as **cosine similarity**: the angle between two vectors in high-dimensional space
- **Try this in Python:**

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")
a = model.encode("The cat sat on the mat")
b = model.encode("A cat rested on a rug")
c = model.encode("The stock market fell 3%")

def cosine(x, y): return np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y))

print(cosine(a, b))  # ~0.85 — similar
print(cosine(a, c))  # ~0.12 — dissimilar
```

### 1.3 Vector Similarity Search

- Brute-force dot-product over millions of vectors is too slow
- **HNSW** (Hierarchical Navigable Small World) — a graph-based index for fast Approximate Nearest Neighbor search. This is the algorithm ChromaDB uses internally.
- **ANN** (Approximate Nearest Neighbor) — "approximate" is fine for RAG; being 5% wrong on retrieval is irrelevant compared to the quality gains
- In `hermes/services/knowledge_service.py` you see `{"hnsw:space": "cosine"}` — this selects cosine similarity as the HNSW distance metric

**✅ Outcome:** You understand *why* the whole system exists.

---

## Phase 2 — The Data Layer: ChromaDB (3–4 days)

*ChromaDB is the right first tool — it's the simplest persistent vector database and is exactly what Hermes uses.*

> **Study in Hermes:** `hermes/services/knowledge_service.py`

### 2.1 ChromaDB Core Concepts

```python
import chromadb

# Persistent — survives process restart (what Hermes uses)
client = chromadb.PersistentClient(path="./data/chromadb")

# Ephemeral — in-memory only, for tests
client = chromadb.EphemeralClient()

# A collection is like a "table" but for vectors
collection = client.get_or_create_collection(
    name="my_knowledge",
    metadata={"hnsw:space": "cosine"}
)
```

### 2.2 The Four Operations

```python
# 1. ADD — store documents with their embeddings
collection.add(
    ids=["chunk_0", "chunk_1"],
    documents=["text of chunk 0", "text of chunk 1"],
    metadatas=[{"source": "file.pdf"}, {"source": "file.pdf"}]
    # embeddings= can be omitted if a collection-level embedding_function is set
)

# 2. QUERY — semantic search
results = collection.query(
    query_texts=["what is machine learning?"],
    n_results=5
)
# results = {"ids":[[...]], "documents":[[...]], "metadatas":[[...]], "distances":[[...]]}

# 3. DELETE — remove by metadata filter
collection.delete(where={"source": "file.pdf"})

# 4. GET — retrieve by id
collection.get(ids=["chunk_0"])
```

### 2.3 Embedding Functions

ChromaDB accepts a custom embedding function object. Hermes defines `_HashEmbeddingFunction` as a **non-semantic fallback** (no model download needed). This is the current biggest limitation:

```python
class _HashEmbeddingFunction(EmbeddingFunction):
    # Converts text → SHA-256 hash → 384 floats
    # NOT semantically meaningful — just for testing
    def __call__(self, input): ...
```

**The upgrade path (Phase 8):**
```python
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
ef = OllamaEmbeddingFunction(url="http://localhost:11434", model_name="nomic-embed-text")
collection = client.get_or_create_collection("hermes_knowledge", embedding_function=ef)
```

### 2.4 Metadata Filtering + Source Attribution

Hermes stores `document_id` and `document_name` in every chunk's metadata:

```python
metadatas = [
    {"document_id": "abc123", "document_name": "manual.pdf", "chunk_index": 0},
    {"document_id": "abc123", "document_name": "manual.pdf", "chunk_index": 1},
]
```

This enables document-level deletion (`where={"document_id": "abc123"}`) and source attribution in answers.

### 2.5 ChromaDB vs. Other Vector Databases

| Database | Type | Best For |
|---|---|---|
| **ChromaDB** ← Hermes uses this | Local embedded | Local-first apps, rapid prototyping |
| Qdrant | Local or cloud server | Production, rich filtering |
| Weaviate | Cloud / self-hosted | Graph features, large scale |
| Pinecone | Cloud-only SaaS | Fully managed, no infra |
| pgvector | Postgres extension | Teams already on Postgres |
| FAISS | Local library | Research, no persistence needed |

ChromaDB was chosen for Hermes because: local-first, zero infrastructure, persistent, Python-native.

**✅ Outcome:** You can explain every line in `KnowledgeService`.

---

## Phase 3 — Chunking: The Hidden Skill (2 days)

*Chunking quality is the single biggest factor in RAG answer quality. Most tutorials skip this entirely.*

> **Study in Hermes:** `hermes/processing/chunking.py`, `hermes/processing/pipeline.py`

### 3.1 Why Chunking Matters

- LLMs have context limits — you can't paste a 300-page book into a prompt
- A **chunk** is the atomic unit of retrieval — if the answer spans two chunks neither of which is retrieved, the LLM cannot answer correctly
- **Too large:** noisy context, lower similarity scores, token limit exceeded
- **Too small:** incomplete context, answer cut off mid-sentence

### 3.2 RecursiveCharacterTextSplitter — What Hermes Uses

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # characters per chunk (from config.yaml)
    chunk_overlap=200,    # overlap between adjacent chunks — preserves context across boundaries
    separators=["\n\n", "\n", ". ", " ", ""]  # tries largest separator first, falls back
)
```

The **overlap** is critical: if an answer straddles a chunk boundary, the overlap ensures both chunks contain enough context to be individually useful.

### 3.3 Chunking Strategies by Document Type

| Document Type | Strategy | Hermes Implementation |
|---|---|---|
| Plain text | Character splitter | `TextParser` → `chunk_text()` |
| Markdown | Split on headings, then character | `MarkdownParser` → `chunk_text()` |
| PDF | Page-by-page, then character | `PDFParser` (PyMuPDF) → `chunk_text()` |
| DOCX | Paragraph-by-paragraph | `DocxParser` (python-docx) → `chunk_text()` |
| Code | Function/class boundaries | `CodeParser` → `chunk_text()` |
| Images | OCR → text → character | `OCRParser` (Tesseract) → `chunk_text()` |

### 3.4 Chunk Metadata

Every `Chunk` in Hermes carries metadata that flows through to ChromaDB:

```python
Chunk(
    text="...the text content...",
    metadata={
        "source": "manual.pdf",       # filename for source attribution
        "doc_type": "pdf",             # parser type used
        "segment_index": 3,            # which page/paragraph this came from
        "chunk_index": 1,              # which chunk within that segment
    }
)
```

**✅ Outcome:** You understand why RAG answers can be bad even with a perfect LLM — it's often the chunking.

---

## Phase 4 — The RAG Pattern End-to-End (3–4 days)

*Wire all components together manually before using LangChain. Understanding the raw pattern makes every abstraction transparent.*

> **Study in Hermes:** `hermes/tools/rag_search.py`, `hermes/services/knowledge_service.py`

### 4.1 Build RAG Without Any Framework

Write this 40-line script from scratch before reading any Hermes code:

```python
import chromadb
import openai  # or use requests to hit Ollama directly

# Setup
client = chromadb.EphemeralClient()
collection = client.create_collection("test")
collection.add(ids=["1","2"], documents=["Python lists are ordered", "Dicts store key-value pairs"])

# Step 1: Embed and retrieve
results = collection.query(query_texts=["how do I store ordered items?"], n_results=2)
chunks = results["documents"][0]

# Step 2: Build prompt with context
context = "\n\n".join(chunks)
prompt = f"Answer based ONLY on this context:\n\n{context}\n\nQuestion: How do I store ordered items in Python?"

# Step 3: Call LLM
# (replace with requests.post("http://localhost:11434/api/chat", ...) for Ollama)
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}]
)
print(response.choices[0].message.content)
```

This is the essence of everything LangChain wraps.

### 4.2 The Retriever-Reader Architecture

Every RAG system has exactly two stages:

```
User Question
     │
     ▼
┌─────────────┐
│  RETRIEVER  │  → Embed question → Query ChromaDB → Return top-k chunks
│  (ChromaDB) │
└──────┬──────┘
       │ relevant text chunks
       ▼
┌─────────────┐
│   READER    │  → Build prompt (question + chunks) → Call LLM → Return answer
│    (LLM)    │
└─────────────┘
       │
       ▼
    Answer + Sources
```

### 4.3 Why RAG Fails — The Three Diagnoses

| Failure Mode | Symptom | Root Cause | Fix |
|---|---|---|---|
| **Retrieval miss** | Answer is in the docs, but LLM says "not found" | Chunking too large/small, bad embeddings | Better chunking + semantic embeddings |
| **Context overload** | LLM gives confused/wrong answer despite retrieving | Too many chunks in prompt | Reduce `top_k`, add re-ranking |
| **Hallucination despite context** | LLM ignores provided context | System prompt doesn't enforce it | Stronger system prompt, temperature=0 |

**✅ Outcome:** You can explain every line in `hermes/tools/rag_search.py` and `knowledge_service.search()`.

---

## Phase 5 — LangChain (5–6 days)

*LangChain is the orchestration glue. Learn it after you understand what it's gluing together.*

> **Study in Hermes:** `hermes/core/agent.py`, `hermes/core/llm_router.py`, `hermes/services/chat_service.py`

### 5.1 Core Abstractions

**`BaseChatModel`** — the interface that Ollama, OpenAI, and Gemini all implement. This is why `LLMRouter` can swap providers without changing any agent code:

```python
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

# All three are BaseChatModel — identical interface
llm = ChatOllama(model="llama3.1", base_url="http://localhost:11434")
llm = ChatOpenAI(model="gpt-4o", api_key="sk-...")
llm = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key="...")
```

**Messages:**
```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="What is Python?"),
    AIMessage(content="Python is a programming language."),
    HumanMessage(content="What version is current?"),
]
```

### 5.2 The `@tool` Decorator

```python
from langchain_core.tools import tool

@tool
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """Search the local knowledge base for information relevant to the query.
    
    Returns the most relevant text passages from ingested documents.
    """
    # The docstring becomes the tool description the LLM sees
    # The type hints become the JSON schema
    results = knowledge.search(query, top_k)
    return format_results(results)
```

In Hermes, `create_rag_search_tool(knowledge)` is a **factory** that closes over the `knowledge` service instance and returns the `@tool`-decorated function. This is done in `hermes/tools/rag_search.py`.

### 5.3 `create_agent` / LangGraph Agents

```python
from langchain.agents import create_agent

# Builds a LangGraph StateGraph internally
graph = create_agent(
    model=llm,          # any BaseChatModel
    tools=[my_tool],    # list of @tool functions
    system_prompt="You are Hermes..."
)

# Non-streaming call
result = await graph.ainvoke({"messages": [HumanMessage(content="...")]})
answer = result["messages"][-1].content

# Streaming call — yields events
async for event in graph.astream_events({"messages": [...]}, version="v2"):
    if event["event"] == "on_chat_model_stream":
        token = event["data"]["chunk"].content
        print(token, end="", flush=True)
```

**The agent loop (ReAct pattern):**
1. LLM receives messages + tool schemas
2. LLM decides: answer directly OR call a tool
3. If tool: LangGraph executes `search_knowledge_base(query=...)`
4. Tool result appended to messages as `ToolMessage`
5. LLM receives updated messages → generates final answer
6. Loop ends

### 5.4 LangChain Package Structure

| Package | Purpose | Used in Hermes |
|---|---|---|
| `langchain-core` | Base classes (BaseChatModel, messages, tools) | `agent.py`, `rag_search.py` |
| `langchain` | `create_agent`, utilities | `agent.py` |
| `langchain-text-splitters` | `RecursiveCharacterTextSplitter` | `chunking.py` |
| `langchain-ollama` | `ChatOllama` | `llm_router.py` |
| `langchain-openai` | `ChatOpenAI` | `llm_router.py` |
| `langchain-google-genai` | `ChatGoogleGenerativeAI` | `llm_router.py` |

> **LangChain version warning:** This project uses LangChain `>=0.3` with `create_agent` (LangGraph-based). Older tutorials use the **deprecated** `AgentExecutor`. Filter out any tutorial using `initialize_agent()` or `AgentExecutor` — that's the old API.

### 5.5 `LLMRouter` Pattern

```python
class LLMRouter:
    def __init__(self):
        self._cache = {}  # lazy init — nothing created at startup

    def get_provider(self, name: str) -> BaseChatModel:
        if name not in self._cache:
            self._cache[name] = self._build(name)  # create once
        return self._cache[name]  # return cached instance
```

`ChatService` goes one level further: one `HermesAgent` per provider name, cached in `self._agents`.

**✅ Outcome:** You can explain every line in `agent.py`, `llm_router.py`, and `chat_service.py`.

---

## Phase 6 — FastAPI (3–4 days)

*The serving layer. Learn this after the core logic — the endpoints are thin wrappers around services.*

> **Study in Hermes:** `hermes/server.py`, `hermes/middleware/auth.py`

### 6.1 FastAPI Fundamentals

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

@app.post("/api/chat")
async def chat(request: ChatRequest):  # Pydantic auto-validates JSON body
    if not request.message:
        raise HTTPException(status_code=422, detail="Empty message")
    return {"answer": "..."}
```

### 6.2 Lifespan Events (Startup / Shutdown)

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: runs before first request
    global _knowledge, _chat_service
    _knowledge = KnowledgeService()
    _chat_service = ChatService(_knowledge, ...)
    
    yield  # server is running here
    
    # SHUTDOWN: runs after last request
    # cleanup (close DB connections etc.)

app = FastAPI(lifespan=lifespan)
```

Why not initialize at module level? Avoids circular imports and ensures `config.yaml` is loaded before any service tries to read it.

### 6.3 Middleware

```python
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Runs before every route handler
        if not authorized(request):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        response = await call_next(request)  # call the actual route handler
        return response
```

The `AuthMiddleware` in Hermes: skip if `auth.enabled=false` → skip if localhost → check `X-API-Key` header → 401 if wrong.

### 6.4 SSE Streaming

```python
from fastapi.responses import StreamingResponse
import asyncio

async def token_generator():
    async for token in chat_service.chat_stream(message):
        yield f"data: {json.dumps({'token': token})}\n\n"
    yield "data: [DONE]\n\n"

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if request.stream:
        return StreamingResponse(
            token_generator(),
            media_type="text/event-stream"
        )
```

SSE format rules: each event is `data: <payload>\n\n` (double newline). The client (browser `EventSource` API or `fetch`) reads events as they arrive.

### 6.5 File Upload

```python
from fastapi import UploadFile, File

@app.post("/api/ingest/upload")
async def upload(file: UploadFile = File(...)):
    contents = await file.read()       # bytes
    # write to temp file, process, clean up
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=Path(file.filename).suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    result = ingest_service.ingest_file(tmp_path)
    Path(tmp_path).unlink()            # clean up
    return result
```

**✅ Outcome:** You can explain every endpoint in `hermes/server.py`.

---

## Phase 7 — Pydantic (1–2 days)

*You're already using it via FastAPI and config.py — this phase makes the patterns explicit.*

> **Study in Hermes:** `hermes/models/api.py`, `hermes/config.py`

### 7.1 Pydantic v2 Models

```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str                         # required
    session_id: str | None = None        # optional, defaults to None
    provider: str | None = None
    stream: bool = False

# Validation is automatic
req = ChatRequest(message="hello")        # OK
req = ChatRequest()                       # ValidationError: message required
req = ChatRequest(message=123)            # OK — Pydantic coerces to "123"
```

### 7.2 Pydantic for Configuration (Nested Models)

```python
class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1"

class LLMConfig(BaseModel):
    default_provider: str = "ollama"
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)

class HermesConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    # ...
```

Access: `get_config().llm.providers.ollama.model` — fully typed, IDE autocomplete works.

**✅ Outcome:** You understand every class in `hermes/models/api.py` and `hermes/config.py`.

---

## Phase 8 — Ollama: Running LLMs Locally (1–2 days)

*The tool that makes Hermes fully local, private, and free.*

> **Prerequisite:** Install Ollama from https://ollama.com/download

### 8.1 What Ollama Is

- A local LLM runtime — one binary that runs quantized GGUF models
- Exposes an OpenAI-compatible REST API at `http://localhost:11434`
- `ollama pull llama3.1` downloads and runs the model (~4.7 GB for 8B Q4)

```bash
# Install and start
ollama serve

# Pull models
ollama pull llama3.1          # chat model
ollama pull nomic-embed-text  # embedding model (critical for Phase 8.3)

# Test it
curl http://localhost:11434/api/chat -d '{"model":"llama3.1","messages":[{"role":"user","content":"hello"}]}'
```

### 8.2 Model Selection for RAG

| Model | Size | Speed | RAG Quality |
|---|---|---|---|
| `llama3.1` (8B) | 4.7 GB | Medium | ★★★★ — recommended |
| `llama3.1` (70B) | 40 GB | Slow | ★★★★★ — if you have the hardware |
| `mistral` (7B) | 4.1 GB | Fast | ★★★ — good for speed |
| `gemma3` (4B) | 3.3 GB | Fast | ★★★ |

For **embeddings** (not chat): `nomic-embed-text` — fast, 768 dimensions, excellent quality.

### 8.3 Upgrading Hermes Embeddings (The Critical Fix)

The current `_HashEmbeddingFunction` produces meaningless similarity scores. The upgrade:

```python
# In knowledge_service.py — replace _HashEmbeddingFunction with:
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

ef = OllamaEmbeddingFunction(
    url="http://localhost:11434",
    model_name="nomic-embed-text"   # from config.yaml → vectordb.embedding_model
)
```

> ⚠️ **Important:** The same embedding model must be used at both **ingest time** and **query time**. If you change the model, you must re-ingest all documents.

**✅ Outcome:** Hermes now does real semantic search. Every previous phase is now fully operational end-to-end.

---

## Phase 9 — MCP Protocol (2–3 days)

*The VS Code Copilot integration. Learn this after everything else — it's just a different transport for the same core logic.*

> **Study in Hermes:** `hermes/mcp_server.py`

### 9.1 What MCP Is

- **Model Context Protocol** — an open standard (Anthropic) for connecting tools to AI assistants
- Three primitives: **Tools** (functions the LLM can call), **Resources** (data it can read), **Prompts** (templated instructions)
- Hermes uses only **Tools** (the most important primitive)
- The same concept as LangChain's `@tool` — but MCP is a transport-level standard, not a library

### 9.2 Transport: stdio vs. HTTP

| Transport | How VS Code connects | Hermes mode |
|---|---|---|
| **stdio** | Spawns Python as child process; communicate over stdin/stdout | `python -m hermes --mcp` |
| HTTP / SSE | Long-lived server, VS Code connects as client | Not used in Hermes |

With stdio, VS Code controls the process lifecycle. No port conflicts, no server management.

### 9.3 FastMCP

```python
from mcp.server import FastMCP

mcp = FastMCP(
    name="hermes",
    instructions="Hermes is a local-first AI knowledge agent..."
)

@mcp.tool()
def search_knowledge(query: str, top_k: int = 5) -> str:
    """Search the local knowledge base for information relevant to the query.
    
    Returns the most relevant text passages from ingested documents.
    """
    # docstring → tool description sent to VS Code Copilot
    # type hints → JSON schema for parameter validation
    results = knowledge.search(query, top_k=top_k)
    return format_results(results)

@mcp.tool()
async def ask_hermes(question: str, provider: str = "") -> str:
    """Ask a question using the full RAG pipeline."""
    response = await chat_service.chat(message=question, provider=provider or None)
    return response.answer

def run_mcp_server():
    import asyncio
    asyncio.run(mcp.run_stdio_async())
```

### 9.4 VS Code Configuration

Add to VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "hermes": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "hermes", "--mcp"],
        "cwd": "C:/Project Hermes"
      }
    }
  }
}
```

VS Code calls `tools/list` on startup and `tools/call` for each tool invocation.

### 9.5 The 5 MCP Tools in Hermes

| Tool | Sync/Async | Description |
|---|---|---|
| `search_knowledge` | sync | Raw vector search — top-k passages, no LLM |
| `ask_hermes` | async | Full RAG pipeline — retrieval + LLM reasoning |
| `ingest_document` | sync | Ingest a file by local path |
| `list_documents` | sync | List all documents in knowledge base |
| `remove_document` | sync | Remove a document by ID |

**`search_knowledge` vs `ask_hermes`:** Use `search_knowledge` when you want to verify what's in the knowledge base or compose your own prompt. Use `ask_hermes` when you want a fully reasoned answer.

**✅ Outcome:** You understand `hermes/mcp_server.py` completely. Adding a new MCP tool takes ~10 lines.

---

## Phase 10 — Advanced RAG (Ongoing)

*This is where good RAG becomes excellent RAG. Tackle these after the core system is working.*

### 10.1 Better Embeddings

| Model | Provider | Dimensions | Notes |
|---|---|---|---|
| `nomic-embed-text` | Ollama (local) | 768 | Best free local option. **Use this first.** |
| `bge-m3` | Ollama (local) | 1024 | Multilingual, excellent quality |
| `text-embedding-3-small` | OpenAI | 1536 | Very high quality, costs money |
| `text-embedding-3-large` | OpenAI | 3072 | Best quality, higher cost |

### 10.2 Re-Ranking

Problem: Vector similarity is a recall measure — it finds vaguely related chunks, not precisely relevant ones.

Solution: After retrieving top-20 chunks by vector similarity, run a **cross-encoder re-ranker** to re-score them and keep only the top-3:

```python
from sentence_transformers import CrossEncoder
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
scores = reranker.predict([(question, chunk) for chunk in chunks])
ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
top_chunks = [c for c, _ in ranked[:3]]
```

### 10.3 Hybrid Search (BM25 + Vector)

- BM25 is keyword-based relevance (classic TF-IDF variant)
- Combined with vector search: BM25 catches exact term matches; vector catches semantic matches
- Critical when users search by proper names, IDs, or specific technical terms

### 10.4 Query Expansion

```python
# Before searching, rewrite the user's question into 3 variants
async def expand_query(question: str, llm) -> list[str]:
    prompt = f"Generate 3 alternative phrasings of: '{question}'"
    result = await llm.ainvoke([HumanMessage(content=prompt)])
    return parse_variants(result.content)

# Search with all variants, deduplicate results
```

### 10.5 Contextual Chunking

Problem: A retrieved chunk may make no sense without its surrounding context.

Solution: Before storing, prepend a brief document/section summary to every chunk:

```
[From: Annual Report 2024 → Section: Revenue by Region]
Revenue in EMEA grew 12% YoY to €4.2B...
```

### 10.6 Evaluation with RAGAS

```bash
pip install ragas
```

```python
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision

results = evaluate(
    questions=test_questions,
    answers=model_answers,
    contexts=retrieved_contexts,
    metrics=[faithfulness, answer_relevancy, context_precision]
)
```

You cannot improve RAG quality without measuring it. RAGAS is the standard tool.

### 10.7 Streaming with Source Citations

Current limitation: `ChatResponse.sources` is always `[]`. The fix: track which tool calls were made during the agent's ReAct loop and extract their document metadata.

---

## Phase 11 — Extending Agents: New Tools, External APIs, and LLM Orchestration (5–7 days)

This is the most practically useful phase for building real-world agents. It covers three interconnected topics:
1. How to add a new `@tool` to the agent
2. How to build tools that call external APIs and the web
3. How to route different tools to different LLMs (orchestration)

---

### 11.1 How the Agent Uses Tools (Conceptual Recap)

Before adding anything, understand the existing flow:

```
User message
    │
    ▼
HermesAgent (LangGraph StateGraph)
    │
    ├── model node  ──► LLM decides: answer directly OR call a tool
    │                        │
    │                        ▼
    └── tools node  ──► executes the chosen @tool, result added to messages
         │
         ▼
    model node again ──► LLM reads tool result, decides next step or final answer
```

The LLM sees tool **names + docstrings** and decides which to call. This means:
- The tool docstring IS the instruction to the LLM — write it clearly
- Tool parameters become structured inputs the LLM fills in
- Tools can be called multiple times or in sequence

**Where tools are registered in Hermes:**

```python
# hermes/tools/rag_search.py  ← tool definition
# hermes/core/agent.py        ← tools list passed to create_agent
# hermes/services/chat_service.py ← agent is built here with the tools list
```

---

### 11.2 Step-by-Step: Adding a New Tool

**Example goal:** Add a tool that calls the Bosch internal REST API to look up a component by part number.

#### Step 1 — Create the tool file

Create `hermes/tools/bosch_api_search.py`:

```python
"""Tool: look up a Bosch component via the internal parts API."""
from __future__ import annotations
from langchain_core.tools import tool

@tool
def bosch_component_lookup(part_number: str) -> str:
    """Look up a Bosch component by part number using the internal parts API.

    Returns component name, description, status, and compatible systems.
    Use this when the user asks about a specific part number or component.
    """
    import httpx

    url = f"https://internal-api.bosch.com/parts/{part_number}"
    r = httpx.get(url, headers={"Authorization": "Bearer ..."}, timeout=10)

    if r.status_code == 404:
        return f"Part number {part_number} not found in the catalog."
    if r.status_code != 200:
        return f"API error {r.status_code}: {r.text[:200]}"

    data = r.json()
    return (
        f"Part: {data['name']}\n"
        f"Description: {data['description']}\n"
        f"Status: {data['status']}\n"
        f"Compatible with: {', '.join(data['compatible_systems'])}"
    )
```

Key rules for tool functions:
- Return a **string** — the LLM reads it as plain text
- Handle all error cases — never raise an exception (the agent will crash)
- The docstring tells the LLM **when** to call this tool — be specific
- Keep parameters simple: strings, ints, floats — no complex objects

#### Step 2 — Register the tool in the agent

Open `hermes/services/chat_service.py` and add the new tool to the list:

```python
# Before (current code)
from hermes.tools.rag_search import build_rag_search_tool

def _get_agent(self, provider: str | None) -> HermesAgent:
    ...
    rag_tool = build_rag_search_tool(self._knowledge)
    agent = HermesAgent(llm=llm, tools=[rag_tool])

# After
from hermes.tools.rag_search import build_rag_search_tool
from hermes.tools.bosch_api_search import bosch_component_lookup

def _get_agent(self, provider: str | None) -> HermesAgent:
    ...
    rag_tool = build_rag_search_tool(self._knowledge)
    agent = HermesAgent(llm=llm, tools=[rag_tool, bosch_component_lookup])
```

That's all. The agent now knows about both tools and will choose between them.

#### Step 3 — Add to the MCP server (optional)

If you also want Copilot to be able to call the tool directly:

```python
# hermes/mcp_server.py
@mcp.tool()
def lookup_component(part_number: str) -> str:
    """Look up a Bosch component by part number."""
    from hermes.tools.bosch_api_search import bosch_component_lookup
    return bosch_component_lookup.invoke({"part_number": part_number})
```

#### Step 4 — Test it

```python
# Quick test without the full server
from hermes.tools.bosch_api_search import bosch_component_lookup
result = bosch_component_lookup.invoke({"part_number": "1234-XYZ"})
print(result)
```

---

### 11.3 Web Search Tool

LangChain has built-in integrations for several search engines. The simplest to add to Hermes:

#### Option A — DuckDuckGo (free, no API key)

```bash
pip install duckduckgo-search
```

```python
# hermes/tools/web_search.py
from langchain_community.tools import DuckDuckGoSearchRun

web_search = DuckDuckGoSearchRun()
# web_search is already a @tool — add directly to agent tools list
```

Register in `chat_service.py`:
```python
from langchain_community.tools import DuckDuckGoSearchRun

def _get_agent(self, provider: str | None) -> HermesAgent:
    ...
    rag_tool = build_rag_search_tool(self._knowledge)
    web_tool = DuckDuckGoSearchRun()
    agent = HermesAgent(llm=llm, tools=[rag_tool, web_tool])
```

The LLM will use `rag_search` for questions about ingested documents and `duckduckgo_search` for questions requiring current/external information. It chooses automatically based on the question context.

#### Option B — Tavily (better quality, requires API key)

```bash
pip install tavily-python
```

```python
from langchain_community.tools.tavily_search import TavilySearchResults

web_tool = TavilySearchResults(
    max_results=5,
    tavily_api_key="your_key"   # or TAVILY_API_KEY env var
)
```

---

### 11.4 LLM Orchestration — Different Models per Tool

**The problem:** You want to use a powerful (slow/expensive) model for complex reasoning but a fast/cheap model for simple lookups.

**Pattern:** Assign a specific LLM to each tool by building a specialized sub-agent or by wrapping the tool to call the LLM directly.

#### Approach 1 — Tool-level LLM selection (simple, recommended)

Each tool calls its own LLM directly instead of relying on the agent's model:

```python
# hermes/tools/web_search.py
from langchain_core.tools import tool
from hermes.core.llm_router import LLMRouter

@tool
def web_search_and_summarize(query: str) -> str:
    """Search the web and return a summarized answer.

    Uses a fast LLM for summarization. Use for current events, recent news,
    or information not in the local knowledge base.
    """
    import httpx

    # Step 1: fetch results (DuckDuckGo or any API)
    r = httpx.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json"},
        timeout=10
    )
    raw_results = r.json().get("AbstractText", "") or r.json().get("RelatedTopics", [{}])[0].get("Text", "no results")

    # Step 2: summarize with a FAST/CHEAP model
    router = LLMRouter()
    fast_llm = router.get_provider("bosch_llm_farm")   # gpt-4o-mini — fast and cheap
    summary = fast_llm.invoke(f"Summarize these search results in 3 sentences:\n{raw_results}")
    return summary.content
```

Meanwhile the reasoning/planning step uses the powerful model configured as `default_provider`.

#### Approach 2 — Agent-level orchestration with LiteLLM

[LiteLLM](https://docs.litellm.ai/) is a proxy that gives a unified OpenAI-compatible interface to 100+ models. It acts as a routing layer:

```bash
pip install litellm
```

```python
# hermes/core/llm_router.py — add a LiteLLM provider
@staticmethod
def _build_litellm(model: str) -> BaseChatModel:
    """Route through LiteLLM proxy for multi-model orchestration."""
    from langchain_openai import ChatOpenAI

    # LiteLLM proxy runs locally on port 4000 by default
    return ChatOpenAI(
        model=model,
        base_url="http://localhost:4000",
        api_key="sk-litellm-key",
    )
```

With LiteLLM you can define routing rules in a config file:

```yaml
# litellm_config.yaml
model_list:
  - model_name: fast        # alias used in your code
    litellm_params:
      model: azure/gpt-4o-mini
      api_key: your_key

  - model_name: powerful    # alias used in your code
    litellm_params:
      model: azure/gpt-4o
      api_key: your_key

router_settings:
  # Automatically use "fast" for short prompts, "powerful" for long ones
  routing_strategy: "latency-based-routing"
```

Then in your tool:
```python
fast_llm = router.get_provider_by_alias("fast")      # → gpt-4o-mini
powerful_llm = router.get_provider_by_alias("powerful")  # → gpt-4o
```

#### Approach 3 — Hermes native: provider-per-task config

The simplest orchestration without external tools — use `config.yaml` to assign default providers per task type:

```yaml
# config.yaml (proposed extension)
llm:
  default_provider: "bosch_llm_farm"        # general chat
  reasoning_provider: "bosch_llm_farm"      # complex tasks (same here, or gpt-4o)
  summarization_provider: "bosch_llm_farm"  # fast summarization tasks
```

Then in tools:
```python
from hermes.config import get_config
from hermes.core.llm_router import LLMRouter

def _get_fast_llm():
    cfg = get_config().llm
    provider = getattr(cfg, "summarization_provider", cfg.default_provider)
    return LLMRouter().get_provider(provider)
```

---

### 11.5 Complete Example — Two-Agent Pipeline

**Goal:** Answer a question by searching both the local knowledge base AND the web, with different LLMs for each, then synthesize a final answer.

```
User: "What is the latest EU regulation on e-bike motor power?"
         │
         ├─► Agent 1 (RAG) ── fast LLM ──► searches ChromaDB → local spec excerpts
         │
         ├─► Agent 2 (Web) ── fast LLM ──► DuckDuckGo → current regulation news
         │
         ▼
    Synthesizer ── powerful LLM ──► combines both results → final answer
```

```python
# hermes/tools/dual_search.py
from langchain_core.tools import tool
from hermes.core.llm_router import LLMRouter

def build_dual_search_tool(knowledge_service):
    router = LLMRouter()
    fast_llm = router.get_provider("bosch_llm_farm")   # gpt-4o-mini

    @tool
    def dual_search(query: str) -> str:
        """Search both local documents AND the web, then synthesize a combined answer.

        Use when the question may need both internal knowledge and current external info.
        """
        from hermes.tools.rag_search import build_rag_search_tool
        from langchain_community.tools import DuckDuckGoSearchRun

        # Search both sources in parallel
        rag_tool = build_rag_search_tool(knowledge_service)
        web_tool = DuckDuckGoSearchRun()

        local_results = rag_tool.invoke({"query": query, "top_k": 3})
        web_results = web_tool.invoke(query)

        # Synthesize with fast LLM
        synthesis_prompt = f"""Combine these two sources to answer: "{query}"

LOCAL KNOWLEDGE BASE:
{local_results}

WEB SEARCH:
{web_results}

Provide a concise, accurate answer citing both sources where relevant."""

        response = fast_llm.invoke(synthesis_prompt)
        return response.content

    return dual_search
```

---

### 11.6 What to Modify — Quick Reference

| Goal | File to modify | What to add |
|---|---|---|
| Add a new tool | `hermes/tools/<new_tool>.py` | New file with `@tool` function |
| Register tool for chat agent | `hermes/services/chat_service.py` | Import + add to `tools=[...]` |
| Register tool for MCP/Copilot | `hermes/mcp_server.py` | New `@mcp.tool()` function |
| Add a new LLM provider | `hermes/core/llm_router.py` | `_build_<name>()` + `_BUILDERS` entry |
| Add provider config | `hermes/config.py` + `config.yaml` | New `*ProviderConfig` model + YAML block |
| Add web search | `hermes/tools/web_search.py` | Use `DuckDuckGoSearchRun` or `TavilySearchResults` |
| Add per-tool LLM | Inside `@tool` function | Call `LLMRouter().get_provider("provider_name")` |
| LiteLLM orchestration | `hermes/core/llm_router.py` | `_build_litellm()` pointing to local LiteLLM proxy |

---

### 11.7 Key Concepts to Understand

**Tool docstring = LLM instruction.** The LLM reads only the name and docstring to decide whether to call a tool. If two tools have similar descriptions, the LLM will pick the wrong one. Make descriptions distinct and precise about when each should be used.

**Tools are synchronous by default.** Use `async def` + `await` inside tools if you need parallel external API calls. LangChain supports async tools.

**Tool errors must be handled inside the tool.** If a tool raises an exception, the entire agent run fails. Always catch exceptions and return a descriptive error string.

**LiteLLM vs native routing.** LiteLLM is powerful but adds infrastructure (a local proxy process). For simple cases — choosing between 2 models based on task type — the native Hermes `LLMRouter` pattern (calling `get_provider("x")` inside the tool) is simpler and has no extra dependencies.

**Cost awareness.** `gpt-4o-mini` costs ~20× less than `gpt-4o` per token. Use it for:
- Web search result summarization
- Simple data extraction  
- Classification/routing decisions

Use the powerful model only for:
- Complex reasoning over long context
- Final answer synthesis
- Code generation

---

## Files to Study (Ordered by Phase)

| Phase | File | What to Focus On |
|---|---|---|
| 2 | `hermes/services/knowledge_service.py` | ChromaDB client, `_HashEmbeddingFunction`, `ingest_file()`, `search()`, metadata structure |
| 3 | `hermes/processing/chunking.py` | `chunk_text()`, splitter config, metadata in `Chunk` |
| 3 | `hermes/processing/pipeline.py` | `DocumentProcessor.process()`, type detection, parser dispatch |
| 4 | `hermes/tools/rag_search.py` | Factory function pattern, `@tool`, context formatting |
| 5 | `hermes/core/agent.py` | `create_agent`, `ainvoke`, `astream_events`, session→messages conversion |
| 5 | `hermes/core/llm_router.py` | Lazy init, `_BUILDERS` dict, `get_default()` |
| 5 | `hermes/services/chat_service.py` | Agent-per-provider cache, `_get_agent()` |
| 6 | `hermes/server.py` | Lifespan, middleware stack, SSE generator, file upload |
| 6 | `hermes/middleware/auth.py` | `BaseHTTPMiddleware`, IP check, header check |
| 7 | `hermes/models/api.py` | All Pydantic schemas |
| 7 | `hermes/config.py` | Nested Pydantic models, env var expansion `${VAR}` |
| 9 | `hermes/mcp_server.py` | `FastMCP`, lazy service init, all 5 tools, sync vs async |
| 11 | `hermes/tools/rag_search.py` | `@tool` decorator, factory pattern, return-string contract |
| 11 | `hermes/core/agent.py` | How tools list is passed into `create_agent` |
| 11 | `hermes/services/chat_service.py` | `_get_agent()` — where to add new tools |
| 11 | `hermes/core/llm_router.py` | `get_provider()` — call inside a tool for per-tool LLM selection |

---

## Summary Timeline

| Phase | Topic | Days | Blocking? |
|---|---|---|---|
| 1 | LLM concepts, embeddings, vector search | 2–3 | Blocks all others |
| 2 | ChromaDB | 3–4 | Blocks 3, 4, 9 |
| 3 | Chunking | 2 | Blocks 4 |
| 4 | Raw RAG pattern | 3–4 | Blocks 5 |
| 5 | LangChain | 5–6 | Blocks 6, 9 |
| 6 | FastAPI | 3–4 | Independent after 5 |
| 7 | Pydantic | 1–2 | Parallel with 6 |
| 8 | Ollama | 1–2 | Unblocks real semantic search |
| 9 | MCP Protocol | 2–3 | Requires 5 |
| 10 | Advanced RAG | Ongoing | After 1–9 |
| 11 | Adding Tools, Agents & LLM Orchestration | 5–7 | After 5 |
| **Total** | | **~37 days** | |

---

*This learning path is tied to the exact code in Project Hermes. Every concept is demonstrated in a real file, not a toy example.*
