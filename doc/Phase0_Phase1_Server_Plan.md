# Project Hermes — Server Implementation Plan
## Phase 0 (Setup) & Phase 1 (Backend Core Logic)

> **Status:** DRAFT — Awaiting approval before implementation  
> **Date:** 2026-03-31  
> **Scope:** Server-side only (UI decisions deferred)

---

## Table of Contents

1. [Vision Analysis & Scope](#1-vision-analysis--scope)
2. [Architecture Overview](#2-architecture-overview)
3. [Design Decisions](#3-design-decisions)
4. [Server Architecture Detail](#4-server-architecture-detail)
5. [Component Design](#5-component-design)
6. [API Design](#6-api-design)
7. [MCP Server Design](#7-mcp-server-design)
8. [Phase 0 — Implementation Steps](#8-phase-0--implementation-steps)
9. [Phase 1 — Implementation Steps](#9-phase-1--implementation-steps)
10. [Project Structure](#10-project-structure)
11. [Open Questions & Deferred Decisions](#11-open-questions--deferred-decisions)

---

## 1. Vision Analysis & Scope

### Core Vision
Hermes is a **local-first AI knowledge agent** — a personal assistant that combines private local data with LLM intelligence while ensuring sensitive documents **never leave the user's machine**.

### What Phase 0+1 Delivers
A fully functional **headless server** that can:

- **Ingest documents** (PDF, TXT, Markdown, DOCX, code files, scanned images) into a local vector database
- **Answer questions** about ingested documents using RAG (Retrieval-Augmented Generation)
- **Maintain conversation context** within a session
- **Connect to three different client types:**
  - Local UI application (via REST API / WebSocket)
  - Cloud-based UI application (via REST API / WebSocket)
  - VS Code Copilot (via MCP — Model Context Protocol)
- **Support pluggable LLM providers:** Ollama (local), OpenAI, Google Gemini
- **Stream responses** token-by-token or return complete responses

### What Is NOT in Scope
- Frontend/UI implementation (deferred)
- Multi-user support (single-user, personal tool)
- Production-grade deployment orchestration
- Advanced agent tools beyond RAG (web search, API calls — future phases)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  User's Local Machine                                               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Local UI App │  │ Cloud UI App │  │ VS Code Copilot (MCP)    │   │
│  │ (future)     │  │ (future)     │  │                          │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘   │
│         │ REST/WS         │ REST/WS               │ MCP (stdio)     │
│         └────────┬────────┘                       │                 │
│                  ▼                                ▼                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   HERMES SERVER                              │   │
│  │  ┌───────────────────────────────────────────────────────┐  │   │
│  │  │              Transport Layer                           │  │   │
│  │  │  ┌─────────────┐  ┌──────────┐  ┌──────────────────┐ │  │   │
│  │  │  │ REST API    │  │ SSE /    │  │ MCP Server       │ │  │   │
│  │  │  │ (FastAPI)   │  │ WebSocket│  │ (stdio transport) │ │  │   │
│  │  │  └──────┬──────┘  └────┬─────┘  └────────┬─────────┘ │  │   │
│  │  └─────────┼──────────────┼──────────────────┼───────────┘  │   │
│  │            └──────────────┼──────────────────┘              │   │
│  │                           ▼                                  │   │
│  │  ┌───────────────────────────────────────────────────────┐  │   │
│  │  │              Core Layer                                │  │   │
│  │  │  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐  │  │   │
│  │  │  │ Agent Engine │  │ LLM Router  │  │    Tool      │  │  │   │
│  │  │  │ (LangChain)  │  │ (pluggable) │  │  Registry    │  │  │   │
│  │  │  └──────────────┘  └─────────────┘  └─────────────┘  │  │   │
│  │  └───────────────────────────────────────────────────────┘  │   │
│  │                           │                                  │   │
│  │  ┌───────────────────────────────────────────────────────┐  │   │
│  │  │              Data Layer                                │  │   │
│  │  │  ┌──────────┐  ┌─────────────┐  ┌──────────────────┐ │  │   │
│  │  │  │ ChromaDB │  │ Doc Store   │  │ Conversation     │ │  │   │
│  │  │  │ (vectors)│  │ (metadata)  │  │ Memory           │ │  │   │
│  │  │  └──────────┘  └─────────────┘  └──────────────────┘ │  │   │
│  │  └───────────────────────────────────────────────────────┘  │   │
│  │                           │                                  │   │
│  │  ┌───────────────────────────────────────────────────────┐  │   │
│  │  │       Document Processing Pipeline                     │  │   │
│  │  │  ┌─────┐ ┌─────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌─────┐ │  │   │
│  │  │  │ PDF │ │ TXT │ │  MD  │ │ DOCX │ │ Code │ │ OCR │ │  │   │
│  │  │  └─────┘ └─────┘ └──────┘ └──────┘ └──────┘ └─────┘ │  │   │
│  │  └───────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                         │
└──────────────────────────┼─────────────────────────────────────────┘
                           │ API calls (only queries + context, never raw docs)
                           ▼
              ┌──────────────────────────┐
              │   Cloud LLM Providers    │
              │  (OpenAI / Gemini)       │
              └──────────────────────────┘
              ┌──────────────────────────┐
              │   Local LLM (Ollama)     │
              │  (runs on same machine)  │
              └──────────────────────────┘
```

---

## 3. Design Decisions

### 3.1 Multi-Transport Server

| Client Type | Protocol | Transport | Notes |
|---|---|---|---|
| Local UI App | HTTP REST + SSE/WebSocket | `localhost:8000` | No auth needed (same machine) |
| Cloud UI App | HTTP REST + SSE/WebSocket | Exposed port (with auth) | API key auth (see §11) |
| VS Code Copilot | MCP (Model Context Protocol) | stdio | Copilot launches Hermes as subprocess |

**Why this approach:** A single server codebase with a shared core layer avoids duplicating logic. The transport layer is a thin adapter over the same service functions.

### 3.2 LLM Provider Strategy

| Provider | Type | Package | Use Case |
|---|---|---|---|
| **Ollama** | Local | `langchain-ollama` | Privacy-maximum mode, no internet needed |
| **OpenAI** | Cloud | `langchain-openai` | GPT-4o, best-in-class reasoning |
| **Google Gemini** | Cloud | `langchain-google-genai` | Gemini Pro, large context window |

Selection via configuration file. Can switch at runtime per conversation.

### 3.3 Document Processing Strategy

| Format | Library | Notes |
|---|---|---|
| PDF | `PyMuPDF` (fitz) | Fast, reliable, preserves layout |
| TXT | Built-in Python | Direct read |
| Markdown | `markdown` / direct read | Parse as plain text with structure |
| DOCX | `python-docx` | Microsoft Word documents |
| Code Files | Built-in Python | `.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, etc. with language-aware chunking |
| Scanned Images / Image PDFs | `Tesseract OCR` via `pytesseract` + `Pillow` | OCR for non-text-selectable content |

### 3.4 Authentication Strategy (Recommendation)

For a personal tool, I recommend a **layered approach** — you can decide the specifics later:

- **Local connections (localhost):** No authentication required. The OS network stack prevents external access.
- **Cloud UI connections:** API key authentication via `X-API-Key` header. Simple, effective, and easy to rotate.
- **MCP connections:** No auth needed — VS Code Copilot launches the server as a local subprocess (stdio transport), so it's inherently secure.

The server will include an **auth middleware** that is:
- **Disabled** for localhost requests
- **Enabled** (API key check) for non-localhost requests
- **Bypassed** for MCP (stdio has no HTTP layer)

> **This is designed so you can decide later.** The middleware is a single toggle in the config.

### 3.5 Streaming Strategy

The server will support **both** response modes:

- **Complete response:** Standard REST `POST` → JSON response (simple, reliable)
- **Streaming (SSE):** `POST` with `Accept: text/event-stream` → Server-Sent Events delivering tokens as they arrive

SSE is preferred over WebSocket for streaming because:
- Simpler to implement and debug
- Works through proxies and firewalls
- One-directional (server→client) is all we need for token streaming
- WebSocket reserved for future bidirectional needs (e.g., real-time collaboration)

---

## 4. Server Architecture Detail

### 4.1 Layer Responsibilities

```
Transport Layer  →  Receives requests, translates protocols, returns responses
     ↓
Core Layer       →  Agent reasoning, LLM orchestration, tool dispatch
     ↓
Data Layer       →  Vector storage, document metadata, conversation history
     ↓
Pipeline Layer   →  Document parsing, chunking, embedding, OCR
```

### 4.2 Dependency Injection

All major components use dependency injection via Python's constructor injection pattern:

```python
# Example: The agent doesn't know or care which LLM it's using
agent = HermesAgent(
    llm=llm_router.get_provider("ollama"),  # or "openai", "gemini"
    tools=[rag_search_tool, ...],
    memory=conversation_memory,
)
```

This makes testing easy (inject mocks) and providers swappable.

---

## 5. Component Design

### 5.1 LLM Router

```python
class LLMRouter:
    """Manages multiple LLM providers. Selects based on config or per-request."""
    
    def get_provider(self, name: str) -> BaseChatModel:
        """Returns configured LangChain ChatModel for the given provider."""
    
    def list_providers(self) -> list[str]:
        """Returns names of available (configured) providers."""
    
    def get_default(self) -> BaseChatModel:
        """Returns the default provider from config."""
```

### 5.2 Document Processor

```python
class DocumentProcessor:
    """Pipeline for converting files → text chunks → embeddings → ChromaDB."""
    
    def ingest(self, file_path: str) -> IngestResult:
        """Full pipeline: detect type → parse → chunk → embed → store."""
    
    def detect_type(self, file_path: str) -> DocumentType:
        """Determine document type from extension + content analysis."""
    
    def parse(self, file_path: str, doc_type: DocumentType) -> list[str]:
        """Extract raw text from document (includes OCR if needed)."""
    
    def chunk(self, text: list[str], doc_type: DocumentType) -> list[Chunk]:
        """Split text into overlapping chunks with metadata."""
```

**Chunking strategy:**
- Default: 1000 tokens with 200 token overlap (RecursiveCharacterTextSplitter)
- Code files: Language-aware splitting (by function/class boundaries)
- Markdown: Header-aware splitting (preserve section structure)

### 5.3 RAG Search Tool

```python
@tool
def search_knowledge_base(query: str, top_k: int = 5) -> str:
    """Search the local knowledge base for information relevant to the query.
    
    Returns the most relevant text passages from ingested documents.
    """
```

### 5.4 Conversation Memory

- In-memory storage per session (dictionary keyed by session ID)
- Configurable history window (default: last 20 messages)
- Future: persist to SQLite for cross-session memory

### 5.5 Configuration

Single YAML configuration file (`config.yaml`):

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  auth:
    enabled: false          # Enable for cloud UI access
    api_key: ""             # Set when auth is enabled

llm:
  default_provider: "ollama"
  providers:
    ollama:
      base_url: "http://localhost:11434"
      model: "llama3.1"
    openai:
      api_key: "${OPENAI_API_KEY}"     # From environment variable
      model: "gpt-4o"
    gemini:
      api_key: "${GEMINI_API_KEY}"
      model: "gemini-pro"

vectordb:
  provider: "chromadb"
  persist_directory: "./data/chromadb"

ingestion:
  chunk_size: 1000
  chunk_overlap: 200
  supported_extensions:
    - ".pdf"
    - ".txt"
    - ".md"
    - ".docx"
    - ".py"
    - ".js"
    - ".ts"
    - ".java"
    - ".c"
    - ".cpp"
    - ".h"
    - ".cs"
    - ".go"
    - ".rs"
    - ".png"
    - ".jpg"
    - ".jpeg"
    - ".tiff"
    - ".bmp"

ocr:
  engine: "tesseract"       # tesseract or easyocr
  language: "eng"
```

---

## 6. API Design

### 6.1 REST Endpoints

#### Chat

```
POST /api/chat
```
**Request:**
```json
{
  "message": "How do I prepare tomatoes for canning?",
  "session_id": "optional-uuid",
  "provider": "ollama",
  "stream": false
}
```
**Response (complete):**
```json
{
  "session_id": "uuid",
  "answer": "To prepare tomatoes for canning...",
  "sources": [
    {"document": "canning-guide.pdf", "page": 42, "chunk": "...relevant text..."}
  ]
}
```
**Response (streaming — `"stream": true`):**
```
Content-Type: text/event-stream

data: {"token": "To"}
data: {"token": " prepare"}
data: {"token": " tomatoes"}
...
data: {"done": true, "sources": [...]}
```

#### Document Ingestion

```
POST /api/ingest
```
**Request:** `multipart/form-data` with file upload, OR:
```json
{
  "file_path": "C:/Users/Documents/canning-guide.pdf"
}
```
**Response:**
```json
{
  "status": "success",
  "document_id": "uuid",
  "document_name": "canning-guide.pdf",
  "chunks_created": 147,
  "processing_time_seconds": 3.2
}
```

#### Document Management

```
GET  /api/documents              — List all ingested documents
GET  /api/documents/{id}         — Get document details
DELETE /api/documents/{id}       — Remove document from knowledge base
```

#### System

```
GET  /api/health                 — Server health check
GET  /api/providers              — List available LLM providers
GET  /api/config                 — Get current (non-sensitive) configuration
```

#### Sessions

```
GET  /api/sessions               — List active sessions
GET  /api/sessions/{id}/history  — Get conversation history
DELETE /api/sessions/{id}        — Clear session
```

---

## 7. MCP Server Design

### 7.1 What is MCP?

The **Model Context Protocol (MCP)** allows AI assistants (like VS Code Copilot) to discover and call external tools. Hermes will expose its capabilities as MCP tools that Copilot can invoke.

### 7.2 MCP Transport

- **Transport:** `stdio` (VS Code Copilot launches `hermes-mcp` as a subprocess)
- **Protocol:** JSON-RPC 2.0 over stdin/stdout
- **Library:** `mcp` Python SDK

### 7.3 VS Code Configuration

Users will add to their VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "hermes": {
        "command": "python",
        "args": ["-m", "hermes.mcp_server"],
        "cwd": "C:/Project Hermes"
      }
    }
  }
}
```

### 7.4 Exposed MCP Tools

| Tool Name | Description | Parameters |
|---|---|---|
| `search_knowledge` | Search the local knowledge base | `query: str`, `top_k: int` |
| `ask_hermes` | Ask a question with full RAG pipeline | `question: str`, `provider: str` |
| `ingest_document` | Add a document to the knowledge base | `file_path: str` |
| `list_documents` | List all ingested documents | — |
| `remove_document` | Remove a document | `document_id: str` |

### 7.5 MCP Server Implementation Approach

```python
# hermes/mcp_server.py
from mcp.server import Server
from mcp.server.stdio import stdio_server

server = Server("hermes")

@server.tool()
async def search_knowledge(query: str, top_k: int = 5) -> str:
    """Search the local knowledge base for relevant information."""
    # Calls the same core service as the REST API
    results = await knowledge_service.search(query, top_k)
    return format_results(results)

@server.tool()
async def ask_hermes(question: str, provider: str = "default") -> str:
    """Ask a question about your local documents."""
    # Same agent pipeline as REST /api/chat
    response = await agent_service.chat(question, provider=provider)
    return response.answer
```

**Key principle:** MCP tools call the **same core services** as the REST API. No logic duplication.

---

## 8. Phase 0 — Implementation Steps

### Step 0.1: Project Scaffolding
- Initialize Python project structure (see §10)
- Create `pyproject.toml` with all dependencies
- Set up virtual environment

### Step 0.2: Configuration System
- Implement YAML config loader with environment variable expansion
- Create default `config.yaml`
- Add config validation (Pydantic models)

### Step 0.3: Development Environment
- Install and verify Ollama is running locally
- Install Tesseract OCR
- Create a `Makefile` or helper scripts for common dev tasks
- Set up basic logging

### Step 0.4: Test Infrastructure
- Set up `pytest` with fixtures
- Create test data directory with sample documents (small PDF, TXT, MD, code file)
- Prepare mock LLM responses for offline testing

**Phase 0 Deliverable:** A runnable project skeleton with configuration, logging, and test infrastructure. No functionality yet.

---

## 9. Phase 1 — Implementation Steps

### Step 1.1: Document Processing Pipeline
Build the ingestion pipeline, one parser at a time:

1. **Text/Markdown parser** (simplest — validate the pipeline end-to-end first)
2. **PDF parser** (PyMuPDF)
3. **DOCX parser** (python-docx)
4. **Code file parser** (language-aware chunking)
5. **OCR engine** (Tesseract for scanned images and image-based PDFs)
6. **Chunking engine** (RecursiveCharacterTextSplitter with type-specific strategies)
7. **Unit tests** for each parser

### Step 1.2: Vector Store Integration
1. Set up ChromaDB with persistent storage
2. Create embedding generation (using Ollama embeddings or sentence-transformers)
3. Implement document store: `add`, `search`, `delete`, `list`
4. Unit tests for vector operations

### Step 1.3: LLM Router
1. Implement Ollama provider adapter
2. Implement OpenAI provider adapter
3. Implement Google Gemini provider adapter
4. Create router with config-based provider selection
5. Test each provider independently

### Step 1.4: RAG Search Tool
1. Implement the LangChain tool wrapper around vector search
2. Implement result formatting with source attribution
3. Test retrieval quality with sample documents

### Step 1.5: Agent Engine
1. Build the LangChain Agent Executor with tool registry
2. Wire up RAG tool + LLM router + conversation memory
3. Test the full pipeline: question → retrieve → generate answer
4. Verify conversation context is maintained across turns

### Step 1.6: REST API Server (FastAPI)
1. Implement FastAPI application with CORS middleware
2. `POST /api/chat` — complete response mode
3. `POST /api/chat` — streaming mode (SSE)
4. `POST /api/ingest` — document ingestion (file path + file upload)
5. `GET/DELETE /api/documents` — document management
6. `GET /api/health`, `GET /api/providers` — system endpoints
7. Session management endpoints
8. Auth middleware (disabled by default, ready for API key mode)
9. Integration tests with `httpx` / `TestClient`

### Step 1.7: MCP Server
1. Implement MCP server with stdio transport
2. Register tools: `search_knowledge`, `ask_hermes`, `ingest_document`, `list_documents`, `remove_document`
3. Wire tools to the same core services as REST API
4. Test MCP server with MCP inspector tool
5. Write VS Code `settings.json` example configuration

### Step 1.8: End-to-End Testing & Documentation
1. Manual end-to-end test via `curl` / Postman (REST API)
2. Manual end-to-end test via VS Code Copilot (MCP)
3. Write `README.md` with setup and usage instructions
4. Write API documentation (auto-generated from FastAPI + manual MCP docs)

**Phase 1 Deliverable:** A fully functional headless server that can ingest documents, answer questions via REST API, stream responses, and integrate with VS Code Copilot via MCP. Testable with `curl` and Copilot — no UI required.

---

## 10. Project Structure

```
Project Hermes/
├── doc/                              # Documentation
│   └── Phase0_Phase1_Server_Plan.md  # This document
├── hermes/                           # Main Python package
│   ├── __init__.py
│   ├── __main__.py                   # Entry point: python -m hermes
│   ├── config.py                     # Configuration loader & models
│   ├── server.py                     # FastAPI application
│   ├── mcp_server.py                 # MCP server (stdio)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py                  # LangChain Agent Engine
│   │   ├── llm_router.py            # Multi-provider LLM router
│   │   └── memory.py                # Conversation memory manager
│   ├── tools/
│   │   ├── __init__.py
│   │   └── rag_search.py            # RAG search tool
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat_service.py          # Chat orchestration
│   │   ├── knowledge_service.py     # Vector store operations
│   │   └── ingest_service.py        # Document ingestion orchestration
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── pipeline.py              # Main processing pipeline
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Abstract parser interface
│   │   │   ├── pdf_parser.py
│   │   │   ├── text_parser.py
│   │   │   ├── markdown_parser.py
│   │   │   ├── docx_parser.py
│   │   │   ├── code_parser.py
│   │   │   └── ocr_parser.py
│   │   └── chunking.py              # Chunking strategies
│   ├── models/
│   │   ├── __init__.py
│   │   ├── api.py                   # Pydantic request/response models
│   │   └── domain.py                # Domain models (Document, Chunk, etc.)
│   └── middleware/
│       ├── __init__.py
│       └── auth.py                  # API key authentication middleware
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Shared fixtures
│   ├── test_data/                   # Sample documents for testing
│   │   ├── sample.pdf
│   │   ├── sample.txt
│   │   ├── sample.md
│   │   └── sample.py
│   ├── unit/
│   │   ├── test_parsers.py
│   │   ├── test_chunking.py
│   │   ├── test_llm_router.py
│   │   └── test_knowledge_service.py
│   └── integration/
│       ├── test_api.py
│       ├── test_ingest_pipeline.py
│       └── test_mcp_server.py
├── data/                             # Runtime data (gitignored)
│   └── chromadb/                     # Vector database storage
├── config.yaml                       # Default configuration
├── pyproject.toml                    # Python project & dependencies
├── Makefile                          # Dev convenience commands
├── README.md                         # Setup & usage guide
├── .env.example                      # Environment variable template
├── .gitignore
└── Vision.md                         # Original vision document
```

---

## 11. Open Questions & Deferred Decisions

| # | Question | Recommendation | Status |
|---|---|---|---|
| 1 | **Cloud UI Authentication** | API key via `X-API-Key` header. Auth middleware is built but disabled by default. Enable in config when you need cloud access. | **Ready to defer** — middleware designed, decide when needed |
| 2 | **Cloud UI Exposure** | For personal use: Cloudflare Tunnel or ngrok (no port forwarding). For shared use: deploy behind reverse proxy with TLS. | **Defer to Phase 2+** |
| 3 | **Embedding model** | Start with Ollama embeddings (e.g., `nomic-embed-text`) for fully local operation. Option to use OpenAI embeddings for better quality. | **Decide during Phase 1.2** |
| 4 | **Conversation persistence** | In-memory for MVP. SQLite add-on planned for cross-session memory. | **Defer to Phase 2** |
| 5 | **Multi-document RAG** | Phase 1 supports multiple documents in one ChromaDB collection. Filtering by document is supported. No cross-collection federation yet. | **Sufficient for Phase 1** |
| 6 | **OCR quality** | Tesseract is free and good enough. EasyOCR is better for non-English. Can swap via config. | **Start with Tesseract** |

---

## Dependencies (pyproject.toml)

```
# Core
fastapi >= 0.115
uvicorn >= 0.30
pydantic >= 2.0
pyyaml >= 6.0

# AI / Agent
langchain >= 0.3
langchain-core >= 0.3
langchain-community >= 0.3
langchain-ollama >= 0.3
langchain-openai >= 0.3
langchain-google-genai >= 2.0
chromadb >= 0.5

# Document Processing
PyMuPDF >= 1.24          # PDF parsing
python-docx >= 1.1       # DOCX parsing
pytesseract >= 0.3       # OCR
Pillow >= 10.0           # Image handling for OCR

# MCP
mcp >= 1.0               # Model Context Protocol SDK

# Utilities
python-multipart >= 0.0.9  # File uploads in FastAPI
httpx >= 0.27              # Async HTTP client
sse-starlette >= 2.0       # SSE support for FastAPI

# Dev / Test
pytest >= 8.0
pytest-asyncio >= 0.24
httpx                      # TestClient
```

---

## Summary

| Aspect | Decision |
|---|---|
| **Language** | Python 3.11+ |
| **API Framework** | FastAPI |
| **Agent Framework** | LangChain |
| **Vector DB** | ChromaDB (local, persistent) |
| **LLM Providers** | Ollama (local) + OpenAI + Gemini (pluggable) |
| **Document Types** | PDF, TXT, MD, DOCX, Code, Scanned Images (OCR) |
| **Client Support** | REST API, SSE streaming, MCP (stdio) |
| **Auth** | API key middleware (deferred activation) |
| **Streaming** | SSE (Server-Sent Events) |
| **Testing** | pytest (unit + integration) |

---

**Next step:** Review this plan and confirm to proceed with implementation of Phase 0.
