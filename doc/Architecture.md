# Project Hermes — Architecture & Design Document

> **Version:** 1.0  
> **Date:** 2026-04-01  
> **Scope:** Phase 0 + Phase 1 server implementation  
> **Purpose:** Code-review reference — maps vision requirements to implementation

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [High-Level Component Architecture](#2-high-level-component-architecture)
3. [Layer Breakdown](#3-layer-breakdown)
4. [Use Case Diagram](#4-use-case-diagram)
5. [Package & Module Structure](#5-package--module-structure)
6. [Class & Data Model Diagrams](#6-class--data-model-diagrams)
7. [Sequence Diagrams — Key Use Cases](#7-sequence-diagrams--key-use-cases)
   - 7.1 [Server Startup](#71-server-startup)
   - 7.2 [Document Ingestion (file upload via REST)](#72-document-ingestion-file-upload-via-rest)
   - 7.3 [Document Ingestion (path via REST)](#73-document-ingestion-path-via-rest)
   - 7.4 [Chat — Non-Streaming Response](#74-chat--non-streaming-response)
   - 7.5 [Chat — Streaming SSE Response](#75-chat--streaming-sse-response)
   - 7.6 [VS Code Copilot — ask_hermes (MCP)](#76-vs-code-copilot--ask_hermes-mcp)
   - 7.7 [VS Code Copilot — search_knowledge (MCP)](#77-vs-code-copilot--search_knowledge-mcp)
   - 7.8 [VS Code Copilot — ingest_document (MCP)](#78-vs-code-copilot--ingest_document-mcp)
8. [Document Processing Pipeline Detail](#8-document-processing-pipeline-detail)
9. [Authentication Flow](#9-authentication-flow)
10. [Configuration & Startup Sequence](#10-configuration--startup-sequence)
11. [State Diagrams](#11-state-diagrams)
12. [Vision-to-Implementation Traceability Matrix](#12-vision-to-implementation-traceability-matrix)
13. [Known Gaps & Phase 2 Candidates](#13-known-gaps--phase-2-candidates)

---

## 1. System Overview

Hermes is a **local-first AI knowledge agent**. Its core promise is that private documents and their vector embeddings **never leave the user's machine**. All reasoning runs locally (Ollama) or the user consciously routes through a cloud LLM with their own API key.

```
Privacy boundary = the user's local machine.
Cloud LLM (OpenAI/Gemini) only receives:
  - the user's question
  - retrieved text chunks (already the user's own data)
  - NO original documents, NO filenames unless the user asks for them
```

The Phase 0+1 deliverable is a **headless server** with three client transports:

| Transport | Protocol | Clients |
|-----------|----------|---------|
| REST API + SSE | HTTP | Local UI app, Cloud-based UI app |
| MCP stdio | JSON-RPC over stdin/stdout | VS Code Copilot |

All three transports share the **same core services** — there is no duplication of business logic.

---

## 2. High-Level Component Architecture

```mermaid
graph TD
    subgraph Clients["Client Layer (future / external)"]
        LocalUI["Local UI App\n(future)"]
        CloudUI["Cloud UI App\n(future)"]
        VSCode["VS Code Copilot\n(MCP client)"]
    end

    subgraph Transport["Transport Layer"]
        REST["FastAPI\nREST API\n:8000"]
        MCP["MCP Server\n(stdio)"]
    end

    subgraph Core["Core Layer"]
        ChatSvc["ChatService"]
        IngestSvc["IngestService"]
        Agent["HermesAgent\n(LangChain)"]
        LLMRouter["LLMRouter"]
        Memory["ConversationMemory"]
        RAGTool["RAG Search Tool"]
    end

    subgraph Data["Data Layer"]
        ChromaDB["ChromaDB\n(vector store)"]
        MemStore["In-Memory\nSession Store"]
    end

    subgraph Pipeline["Document Processing Pipeline"]
        Processor["DocumentProcessor"]
        TextP["TextParser"]
        MarkdownP["MarkdownParser"]
        PDFP["PDFParser"]
        DocxP["DocxParser"]
        CodeP["CodeParser"]
        OCRP["OCRParser"]
        Chunker["chunk_text()\nRecursiveCharacterTextSplitter"]
    end

    subgraph LLMs["LLM Providers (external)"]
        Ollama["Ollama\n(local)"]
        OpenAI["OpenAI API\n(cloud)"]
        Gemini["Google Gemini\n(cloud)"]
    end

    LocalUI -->|REST/SSE| REST
    CloudUI -->|REST/SSE| REST
    VSCode -->|stdio JSON-RPC| MCP

    REST --> ChatSvc
    REST --> IngestSvc
    MCP --> ChatSvc
    MCP --> KnowledgeSvc["KnowledgeService"]

    ChatSvc --> Agent
    ChatSvc --> LLMRouter
    ChatSvc --> Memory
    IngestSvc --> KnowledgeSvc

    Agent --> RAGTool
    Agent --> LLMRouter
    Agent --> Memory
    RAGTool --> KnowledgeSvc

    KnowledgeSvc --> ChromaDB
    KnowledgeSvc --> Processor
    Memory --> MemStore

    Processor --> TextP
    Processor --> MarkdownP
    Processor --> PDFP
    Processor --> DocxP
    Processor --> CodeP
    Processor --> OCRP
    TextP --> Chunker
    MarkdownP --> Chunker
    PDFP --> Chunker
    DocxP --> Chunker
    CodeP --> Chunker
    OCRP --> Chunker

    LLMRouter --> Ollama
    LLMRouter --> OpenAI
    LLMRouter --> Gemini
```

---

## 3. Layer Breakdown

### 3.1 Transport Layer

| Module | File | Role |
|--------|------|------|
| `server.py` | `hermes/server.py` | FastAPI app — REST endpoints, SSE streaming, CORS, auth middleware wiring, lifespan startup/shutdown |
| `mcp_server.py` | `hermes/mcp_server.py` | `FastMCP` server — exposes 5 tools callable by VS Code Copilot over stdio |

The two transports are **independent processes**. The user either runs:
- `python -m hermes` → HTTP server (for UI clients)
- `python -m hermes --mcp` → stdio MCP server (for VS Code)

### 3.2 Core Layer

| Module | File | Role |
|--------|------|------|
| `ChatService` | `hermes/services/chat_service.py` | Creates/caches `HermesAgent` per provider; routes `chat()` and `chat_stream()` calls |
| `IngestService` | `hermes/services/ingest_service.py` | Thin wrapper — validates file existence, delegates to `KnowledgeService` |
| `KnowledgeService` | `hermes/services/knowledge_service.py` | All vector-store operations: ingest, search, list, delete |
| `HermesAgent` | `hermes/core/agent.py` | LangChain `create_agent` graph — builds message list, invokes LLM + tools, saves to memory |
| `LLMRouter` | `hermes/core/llm_router.py` | Lazy-init & cache of provider instances (Ollama / OpenAI / Gemini) |
| `ConversationMemory` | `hermes/core/memory.py` | In-memory session map: `session_id → Session(messages[])` |
| `RAG Search Tool` | `hermes/tools/rag_search.py` | LangChain `@tool` factory that closes over `KnowledgeService` |

### 3.3 Data Layer

| Storage | Technology | Persistence |
|---------|-----------|-------------|
| Vector store | ChromaDB (embedded) | Persistent — `./data/chromadb/` |
| Conversation sessions | Python `dict` in `ConversationMemory` | In-memory only — lost on restart |

### 3.4 Document Processing Pipeline

| Module | File | Role |
|--------|------|------|
| `DocumentProcessor` | `hermes/processing/pipeline.py` | Detects type, finds parser, runs parse → chunk |
| `TextParser` | `hermes/processing/parsers/text_parser.py` | `.txt` files |
| `MarkdownParser` | `hermes/processing/parsers/markdown_parser.py` | `.md` / `.markdown` |
| `PDFParser` | `hermes/processing/parsers/pdf_parser.py` | `.pdf` via `pymupdf` |
| `DocxParser` | `hermes/processing/parsers/docx_parser.py` | `.docx` via `python-docx` |
| `CodeParser` | `hermes/processing/parsers/code_parser.py` | Source code files (14 extensions) |
| `OCRParser` | `hermes/processing/parsers/ocr_parser.py` | Images via Tesseract |
| `chunk_text()` | `hermes/processing/chunking.py` | LangChain `RecursiveCharacterTextSplitter` — 1000 char / 200 overlap |

---

## 4. Use Case Diagram

```mermaid
graph TD
    subgraph Actors
        LocalUser["👤 Local User\n(UI App)"]
        CloudUser["🌐 Remote User\n(Cloud UI App)"]
        CopilotUser["💻 Developer\n(VS Code Copilot)"]
    end

    subgraph System["Hermes Server"]
        UC1["UC1: Ingest Document\n(file upload)"]
        UC2["UC2: Ingest Document\n(by path)"]
        UC3["UC3: Chat — Ask Question\n(non-streaming)"]
        UC4["UC4: Chat — Ask Question\n(SSE streaming)"]
        UC5["UC5: List Documents"]
        UC6["UC6: Remove Document"]
        UC7["UC7: View Conversation History"]
        UC8["UC8: Clear Session"]
        UC9["UC9: List LLM Providers"]
        UC10["UC10: Health Check"]
        UC11["UC11: Search Knowledge Base\n(MCP)"]
        UC12["UC12: Ask Hermes with RAG\n(MCP)"]
        UC13["UC13: Ingest Document\n(MCP)"]
        UC14["UC14: List Documents\n(MCP)"]
        UC15["UC15: Remove Document\n(MCP)"]
    end

    LocalUser --> UC1
    LocalUser --> UC2
    LocalUser --> UC3
    LocalUser --> UC4
    LocalUser --> UC5
    LocalUser --> UC6
    LocalUser --> UC7
    LocalUser --> UC8
    LocalUser --> UC9
    LocalUser --> UC10

    CloudUser --> UC3
    CloudUser --> UC4
    CloudUser --> UC5
    CloudUser --> UC10

    CopilotUser --> UC11
    CopilotUser --> UC12
    CopilotUser --> UC13
    CopilotUser --> UC14
    CopilotUser --> UC15
```

> **Note on Cloud UI Auth:** `UC3`, `UC4`, `UC5` are available over REST to cloud clients, but all non-localhost requests require an `X-API-Key` header when `auth.enabled = true` in `config.yaml`.

---

## 5. Package & Module Structure

```mermaid
graph LR
    subgraph hermes["hermes/ (package)"]
        init["__init__.py\nversion = 0.1.0"]
        main["__main__.py\nCLI entry point\nmain()"]
        config["config.py\nHermesConfig\nload_config()\nget_config()"]
        logging_mod["logging.py\nsetup_logging()\nget_logger()"]
        server["server.py\nFastAPI app\nlifespan()"]
        mcp["mcp_server.py\nFastMCP instance\nrun_mcp_server()"]
    end

    subgraph models["hermes/models/"]
        domain["domain.py\nChunk, IngestResult\nDocumentRecord\nSearchResult\nChatResponse\nDocumentType"]
        api_models["api.py\nPydantic schemas\nChatRequest/Response\nIngestResponse\nDocumentListResponse"]
    end

    subgraph core["hermes/core/"]
        agent["agent.py\nHermesAgent\nchat()\nchat_stream()"]
        llm_router["llm_router.py\nLLMRouter\nget_provider()\nget_default()"]
        memory["memory.py\nConversationMemory\nSession, Message"]
    end

    subgraph services["hermes/services/"]
        chat_svc["chat_service.py\nChatService\nchat()\nchat_stream()"]
        ingest_svc["ingest_service.py\nIngestService\ningest_file()"]
        knowledge_svc["knowledge_service.py\nKnowledgeService\ningest_file()\nsearch()\nlist_documents()\ndelete_document()"]
    end

    subgraph tools["hermes/tools/"]
        rag["rag_search.py\ncreate_rag_search_tool()\n@tool search_knowledge_base()"]
    end

    subgraph processing["hermes/processing/"]
        pipeline["pipeline.py\nDocumentProcessor\nprocess()\ndetect_type()"]
        chunking["chunking.py\nchunk_text()"]
        subgraph parsers["parsers/"]
            base["base.py\nBaseParser (ABC)\nparse()\nsupports()"]
            txt["text_parser.py"]
            md["markdown_parser.py"]
            pdf["pdf_parser.py"]
            docx["docx_parser.py"]
            code["code_parser.py"]
            ocr["ocr_parser.py"]
        end
    end

    subgraph middleware["hermes/middleware/"]
        auth["auth.py\nAuthMiddleware\ndispatch()"]
    end

    main --> config
    main --> server
    main --> mcp
    server --> chat_svc
    server --> ingest_svc
    server --> knowledge_svc
    server --> auth
    mcp --> chat_svc
    mcp --> knowledge_svc
    chat_svc --> agent
    chat_svc --> llm_router
    chat_svc --> memory
    agent --> rag
    agent --> llm_router
    agent --> memory
    rag --> knowledge_svc
    ingest_svc --> knowledge_svc
    knowledge_svc --> pipeline
    knowledge_svc --> domain
    pipeline --> chunking
    pipeline --> base
    base --> txt
    base --> md
    base --> pdf
    base --> docx
    base --> code
    base --> ocr
```

---

## 6. Class & Data Model Diagrams

### 6.1 Domain Models

```mermaid
classDiagram
    class DocumentType {
        <<enumeration>>
        TEXT
        MARKDOWN
        PDF
        DOCX
        CODE
        IMAGE
    }

    class Chunk {
        +str text
        +dict metadata
    }

    class IngestResult {
        +str document_id
        +str document_name
        +DocumentType doc_type
        +int chunks_created
        +float processing_time_seconds
    }

    class DocumentRecord {
        +str document_id
        +str name
        +str file_path
        +DocumentType doc_type
        +int chunks_count
        +datetime ingested_at
    }

    class SearchResult {
        +str text
        +str document_name
        +float score
        +dict metadata
    }

    class ChatResponse {
        +str answer
        +str session_id
        +list~SearchResult~ sources
    }

    class Message {
        +str role
        +str content
    }

    class Session {
        +str session_id
        +list~Message~ messages
        +int max_history
        +add(role, content)
        +get_history() list
        +clear()
    }

    IngestResult --> DocumentType
    DocumentRecord --> DocumentType
    Chunk --> "0..*" DocumentType : typed via metadata
    Session "1" --> "0..*" Message
    ChatResponse --> "0..*" SearchResult
```

### 6.2 Service & Core Classes

```mermaid
classDiagram
    class KnowledgeService {
        -PersistentClient _client
        -Collection _collection
        -DocumentProcessor _processor
        +ingest_file(file_path) IngestResult
        +search(query, top_k) list~SearchResult~
        +list_documents() list~DocumentRecord~
        +delete_document(document_id) bool
        +ingest_bytes(name, data, ext) IngestResult
    }

    class IngestService {
        -KnowledgeService _knowledge
        +ingest_file(file_path) IngestResult
    }

    class LLMRouter {
        -dict _cache
        +get_provider(name) BaseChatModel
        +get_default() BaseChatModel
        +list_providers() list~str~
        +is_available(name) bool
        -_build_ollama() ChatOllama
        -_build_openai() ChatOpenAI
        -_build_gemini() ChatGoogleGenerativeAI
    }

    class ConversationMemory {
        -dict _sessions
        +get_or_create_session(session_id) Session
        +get_session(session_id) Session
        +delete_session(session_id) bool
        +list_sessions() list~str~
    }

    class HermesAgent {
        -ConversationMemory _memory
        -CompiledGraph _graph
        +chat(message, session_id) ChatResponse
        +chat_stream(message, session_id) AsyncIterator~str~
    }

    class ChatService {
        -KnowledgeService _knowledge
        -LLMRouter _llm_router
        -ConversationMemory _memory
        -dict _agents
        +chat(message, session_id, provider) ChatResponse
        +chat_stream(message, session_id, provider) AsyncIterator~str~
        -_get_agent(provider) HermesAgent
    }

    class DocumentProcessor {
        -list _parsers
        +process(file_path) tuple
        +detect_type(file_path) DocumentType
        +is_supported(file_path) bool
        -_get_parser(file_path) BaseParser
    }

    class BaseParser {
        <<abstract>>
        +parse(file_path) list~str~
        +supports(file_path) bool
    }

    ChatService --> HermesAgent : creates/caches
    ChatService --> LLMRouter
    ChatService --> ConversationMemory
    HermesAgent --> ConversationMemory
    HermesAgent --> LLMRouter : via tool/llm ref
    IngestService --> KnowledgeService
    KnowledgeService --> DocumentProcessor
    DocumentProcessor --> BaseParser
    ConversationMemory --> "0..*" Session
```

### 6.3 API Schema Models (Pydantic)

```mermaid
classDiagram
    class ChatRequest {
        +str message
        +str|None session_id
        +str|None provider
        +bool stream
    }

    class ChatResponse_API {
        +str session_id
        +str answer
        +list~SourceInfo~ sources
    }

    class SourceInfo {
        +str document
        +str chunk
        +float score
    }

    class IngestResponse {
        +str status
        +str document_id
        +str document_name
        +int chunks_created
        +float processing_time_seconds
    }

    class IngestByPathRequest {
        +str file_path
    }

    class DocumentInfo {
        +str document_id
        +str name
        +str doc_type
        +int chunks_count
        +str ingested_at
    }

    class DocumentListResponse {
        +list~DocumentInfo~ documents
    }

    class HealthResponse {
        +str status
        +str version
    }

    class ProvidersResponse {
        +str default
        +list~ProviderInfo~ providers
    }

    class ProviderInfo {
        +str name
        +bool available
    }

    ChatResponse_API --> "0..*" SourceInfo
    DocumentListResponse --> "0..*" DocumentInfo
    ProvidersResponse --> "0..*" ProviderInfo
```

---

## 7. Sequence Diagrams — Key Use Cases

### 7.1 Server Startup

```mermaid
sequenceDiagram
    participant CLI as python -m hermes
    participant Main as __main__.py main()
    participant Config as config.py load_config()
    participant Log as logging.py setup_logging()
    participant Uvicorn as uvicorn
    participant App as server.py lifespan()
    participant KS as KnowledgeService()
    participant LLM as LLMRouter()
    participant Mem as ConversationMemory()
    participant CS as ChatService()
    participant IS as IngestService()

    CLI->>Main: parse args (--host, --port, --config)
    Main->>Config: load_config(path)
    Config-->>Main: HermesConfig
    Main->>Log: setup_logging()
    Main->>Uvicorn: uvicorn.run("hermes.server:app", host, port)
    Uvicorn->>App: lifespan(app) — startup
    App->>KS: KnowledgeService()
    KS-->>App: ready (ChromaDB opened)
    App->>LLM: LLMRouter()
    LLM-->>App: ready (no providers loaded yet — lazy)
    App->>Mem: ConversationMemory()
    Mem-->>App: ready (empty session map)
    App->>CS: ChatService(knowledge, llm_router, memory)
    CS-->>App: ready
    App->>IS: IngestService(knowledge)
    IS-->>App: ready
    App-->>Uvicorn: yield (server now accepting requests)
```

### 7.2 Document Ingestion (file upload via REST)

```mermaid
sequenceDiagram
    participant Client as UI Client
    participant Auth as AuthMiddleware
    participant API as POST /api/ingest/upload
    participant IS as IngestService
    participant KS as KnowledgeService
    participant DP as DocumentProcessor
    participant Parser as Appropriate Parser
    participant Chunker as chunk_text()
    participant DB as ChromaDB

    Client->>Auth: POST /api/ingest/upload\nmultipart/form-data (file bytes)
    Auth->>Auth: check auth.enabled + client IP
    Auth->>API: pass through
    API->>API: save bytes to temp file
    API->>IS: ingest_file(temp_path)
    IS->>IS: verify file exists
    IS->>KS: ingest_file(path)
    KS->>DP: process(path)
    DP->>DP: detect_type(path) → DocumentType
    DP->>DP: _get_parser(path) → Parser
    DP->>Parser: parse(path) → list[str] segments
    Parser-->>DP: ["segment1", "segment2", ...]
    DP->>Chunker: chunk_text(segments, source_name, doc_type)
    Chunker->>Chunker: RecursiveCharacterTextSplitter 1000/200
    Chunker-->>DP: list[Chunk]
    DP-->>KS: (list[Chunk], DocumentType)
    KS->>KS: generate doc_id = uuid.hex[:12]
    KS->>DB: collection.add(ids, documents, metadatas)
    DB-->>KS: stored
    KS-->>IS: IngestResult(doc_id, name, type, chunks, time)
    IS-->>API: IngestResult
    API-->>Client: 200 OK\n{"document_id":"...", "chunks_created":42, ...}
    API->>API: cleanup temp file
```

### 7.3 Document Ingestion (path via REST)

```mermaid
sequenceDiagram
    participant Client as Local UI Client
    participant Auth as AuthMiddleware
    participant API as POST /api/ingest/path
    participant IS as IngestService
    participant KS as KnowledgeService

    Client->>Auth: POST /api/ingest/path\n{"file_path": "/home/user/doc.pdf"}
    Auth->>API: pass through (localhost)
    API->>IS: ingest_file(file_path)
    IS->>IS: Path(file_path).is_file() — raises 404 if missing
    IS->>KS: ingest_file(path)
    Note over KS: same pipeline as UC2 (steps omitted)
    KS-->>IS: IngestResult
    IS-->>API: IngestResult
    API-->>Client: 200 OK IngestResponse
```

> **Security note:** Path-by-path ingestion is intended for localhost clients only. The `AuthMiddleware` does not apply extra restrictions to paths — the operator should only expose port 8000 to trusted networks.

### 7.4 Chat — Non-Streaming Response

```mermaid
sequenceDiagram
    participant Client as UI Client
    participant Auth as AuthMiddleware
    participant API as POST /api/chat
    participant CS as ChatService
    participant Agent as HermesAgent
    participant Mem as ConversationMemory
    participant RAG as search_knowledge_base()
    participant KS as KnowledgeService
    participant DB as ChromaDB
    participant LLM as LLMRouter → BaseChatModel

    Client->>Auth: POST /api/chat\n{"message":"...", "session_id":"abc", "stream":false}
    Auth->>API: pass through
    API->>CS: chat(message, session_id, provider)
    CS->>CS: _get_agent(provider) — create or reuse
    CS->>Agent: agent.chat(message, session_id="abc")
    Agent->>Mem: get_or_create_session("abc")
    Mem-->>Agent: Session(history=[...])
    Agent->>Agent: _session_to_messages(session) → LangChain messages
    Agent->>Agent: append HumanMessage(message)
    Agent->>LLM: graph.ainvoke({messages: [...]})

    Note over LLM: LLM decides to call tool
    LLM->>RAG: search_knowledge_base(query="...")
    RAG->>KS: knowledge.search(query, top_k=5)
    KS->>DB: collection.query(query_texts, n_results=5)
    DB-->>KS: matched chunks + metadata
    KS-->>RAG: list[SearchResult]
    RAG-->>LLM: formatted text with sources

    Note over LLM: LLM generates final answer
    LLM-->>Agent: {messages: [..., AIMessage(content="answer")]}
    Agent->>Agent: extract last AIMessage.content
    Agent->>Mem: session.add("human", message)
    Agent->>Mem: session.add("ai", answer)
    Agent-->>CS: ChatResponse(answer, session_id, sources=[])
    CS-->>API: ChatResponse
    API-->>Client: 200 OK\n{"session_id":"abc", "answer":"...", "sources":[]}
```

### 7.5 Chat — Streaming SSE Response

```mermaid
sequenceDiagram
    participant Client as UI Client (SSE consumer)
    participant API as POST /api/chat (stream=true)
    participant CS as ChatService
    participant Agent as HermesAgent
    participant LLM as BaseChatModel (streaming)

    Client->>API: POST /api/chat\n{"message":"...", "stream":true}
    API->>API: detect stream=true → return StreamingResponse

    loop SSE token stream
        API->>CS: chat_stream(message, session_id, provider)
        CS->>Agent: agent.chat_stream(message, session_id)
        Agent->>LLM: graph.astream_events({messages}, version="v2")
        LLM-->>Agent: event {event:"on_chat_model_stream", data:{chunk}}
        Agent->>Agent: extract chunk.content token
        Agent-->>CS: yield token
        CS-->>API: yield token
        API-->>Client: data: {"token": "Hello"}\n\n
    end

    Agent->>Agent: stream ends → save full answer to session memory
    API-->>Client: data: [DONE]\n\n (stream closed)
```

> SSE format: each event is `data: {"token": "..."}` followed by `\n\n`. The client reconnects automatically if the connection drops (SSE protocol).

### 7.6 VS Code Copilot — `ask_hermes` (MCP)

```mermaid
sequenceDiagram
    participant Copilot as VS Code Copilot
    participant MCP as mcp_server.py (stdio)
    participant Init as _init_services()
    participant CS as ChatService
    participant Agent as HermesAgent
    participant RAG as RAG Tool
    participant KS as KnowledgeService
    participant LLM as LLMRouter → LLM

    Note over Copilot,MCP: VS Code launches: python -m hermes --mcp
    Copilot->>MCP: tools/list (JSON-RPC)
    MCP-->>Copilot: [ask_hermes, search_knowledge, ingest_document, list_documents, remove_document]

    Copilot->>MCP: tools/call {name:"ask_hermes",\nargs:{question:"What is X?", provider:""}}
    MCP->>Init: _init_services() — lazy init on first call
    Init-->>MCP: (KnowledgeService, ChatService)
    MCP->>CS: chat_service.chat(question, provider=None)
    CS->>Agent: agent.chat(question, session_id=None)
    Agent->>LLM: ainvoke with RAG tool
    LLM->>RAG: search_knowledge_base("What is X?")
    RAG->>KS: search(query)
    KS-->>RAG: results
    RAG-->>LLM: formatted context
    LLM-->>Agent: answer
    Agent-->>CS: ChatResponse
    CS-->>MCP: ChatResponse.answer
    MCP-->>Copilot: tool result (string)
    Copilot->>Copilot: uses answer as context in its response
```

> **MCP transport:** VS Code spawns Hermes as a **child process**. All communication is over stdin/stdout as JSON-RPC messages. No network port is used. Services are lazily initialized on the first tool call.

### 7.7 VS Code Copilot — `search_knowledge` (MCP)

```mermaid
sequenceDiagram
    participant Copilot as VS Code Copilot
    participant MCP as mcp_server.py
    participant KS as KnowledgeService
    participant DB as ChromaDB

    Copilot->>MCP: tools/call {name:"search_knowledge",\nargs:{query:"embedding models", top_k:5}}
    MCP->>KS: knowledge.search("embedding models", top_k=5)
    KS->>DB: collection.query(query_texts=["..."], n_results=5)
    DB-->>KS: {documents:[], metadatas:[], distances:[]}
    KS->>KS: build list[SearchResult]
    KS-->>MCP: list[SearchResult]
    MCP->>MCP: format as numbered text blocks with source attribution
    MCP-->>Copilot: "[1] (Source: doc.pdf, score: 0.87)\n..."
```

> **Difference from `ask_hermes`:** `search_knowledge` returns raw retrieved passages. No LLM is called. This is useful when the developer wants to verify what's in the knowledge base, or wants to compose their own prompt in Copilot.

### 7.8 VS Code Copilot — `ingest_document` (MCP)

```mermaid
sequenceDiagram
    participant Copilot as VS Code Copilot
    participant MCP as mcp_server.py
    participant KS as KnowledgeService
    participant Pipeline as DocumentProcessor

    Copilot->>MCP: tools/call {name:"ingest_document",\nargs:{file_path:"/home/user/notes.md"}}
    MCP->>KS: knowledge.ingest_file(file_path)
    KS->>Pipeline: process(path)
    Pipeline-->>KS: (chunks, doc_type)
    KS->>KS: ChromaDB collection.add(...)
    KS-->>MCP: IngestResult
    MCP-->>Copilot: "Successfully ingested 'notes.md'\n  Chunks created: 12\n  ..."
```

---

## 8. Document Processing Pipeline Detail

```mermaid
flowchart TD
    A["File Path"] --> B{"is_supported?"}
    B -->|No| ERR1["raise ValueError - Unsupported file type"]
    B -->|Yes| C{"detect_type from extension map"}
    C --> D{"find parser via _get_parser()"}

    D --> P1["TextParser .txt"]
    D --> P2["MarkdownParser .md"]
    D --> P3["PDFParser .pdf - pymupdf page-by-page"]
    D --> P4["DocxParser .docx - python-docx paragraphs"]
    D --> P5["CodeParser .py .js .ts .java .c .cpp .go .rs"]
    D --> P6["OCRParser .png .jpg .jpeg - pytesseract"]

    P1 --> SEG["list of str segments - logical text units"]
    P2 --> SEG
    P3 --> SEG
    P4 --> SEG
    P5 --> SEG
    P6 --> SEG

    SEG --> CHUNK["chunk_text - RecursiveCharacterTextSplitter\nchunk_size=1000, overlap=200"]

    CHUNK --> CHUNKS["list of Chunk objects\ntext + metadata: source, doc_type, segment_index, chunk_index"]

    CHUNKS --> STORE["KnowledgeService\ncollection.add - ids, documents, metadatas"]

    STORE --> DB["ChromaDB PersistentClient\n./data/chromadb/"]
```

### 8.1 Embedding Strategy

The current implementation uses a **`_HashEmbeddingFunction`** (SHA-256 hash → 384-dimensional float vector). This is a **non-semantic fallback** that avoids requiring model downloads in offline/corporate environments.

```
For real semantic search (recommended for production):
  Option A: OllamaEmbeddingFunction (local, no cost)
            model: "nomic-embed-text" (set in config.yaml → vectordb.embedding_model)
  Option B: OpenAIEmbeddingFunction (cloud, cost per token)
  
This is a Phase 2 upgrade — pass the embedding function to KnowledgeService(embedding_fn=...).
```

---

## 9. Authentication Flow

```mermaid
flowchart TD
    REQ["Incoming HTTP Request"] --> MW["AuthMiddleware.dispatch()"]
    MW --> CHECK1{auth.enabled\nin config.yaml?}
    CHECK1 -->|False| PASS["call_next(request)\nRequest passes through"]
    CHECK1 -->|True| CHECK2{client host\nin localhost set?\n127.0.0.1 ::1 localhost}
    CHECK2 -->|Yes| PASS
    CHECK2 -->|No| CHECK3{X-API-Key header\nmatches config api_key?}
    CHECK3 -->|Yes| PASS
    CHECK3 -->|No - missing or wrong| DENY["401 Unauthorized\n{detail: Invalid or missing API key}"]
    PASS --> HANDLER["Route Handler\n(processes request)"]
```

**Default state:** `auth.enabled = false` — all requests pass through. Set `auth.enabled = true` and `auth.api_key = <secret>` in `config.yaml` (or via `${HERMES_API_KEY}` env var) to protect cloud-accessible deployments.

---

## 10. Configuration & Startup Sequence

```mermaid
flowchart LR
    subgraph Sources["Config Sources (priority: env > yaml > defaults)"]
        YAML["config.yaml\n(base values)"]
        ENV["Environment variables\n${VAR_NAME} in yaml values\ne.g. ${OPENAI_API_KEY}"]
        CODE["Pydantic defaults\nin HermesConfig model"]
    end

    subgraph Structure["HermesConfig"]
        Server["server:\n  host, port\n  auth.enabled, auth.api_key"]
        LLMConf["llm:\n  default_provider\n  providers:\n    ollama: {base_url, model}\n    openai: {api_key, model}\n    gemini: {api_key, model}"]
        VDB["vectordb:\n  provider\n  persist_directory\n  embedding_model"]
        Ingest["ingestion:\n  chunk_size (1000)\n  chunk_overlap (200)\n  supported_extensions"]
        OCRConf["ocr:\n  engine (tesseract)\n  language (eng)"]
        Logging["logging:\n  level, format"]
    end

    ENV --> YAML
    YAML --> Structure
    CODE --> Structure
    Structure --> App["get_config()\nsingleton — cached after\nfirst load_config() call"]
```

---

## 11. State Diagrams

### 11.1 Session State

```mermaid
stateDiagram-v2
    [*] --> NonExistent : new connection
    NonExistent --> Active : first message received\nget_or_create_session(None)\nnew UUID generated
    NonExistent --> Active : client provides session_id\nget_or_create_session("abc")
    Active --> Active : message added\nsession.add(role, content)
    Active --> Active : history trimmed\nif len > max_history (20)
    Active --> NonExistent : delete_session(session_id)
    Active --> Active : clear()\nClear history, keep session
    Active --> [*] : server restart\n(in-memory — sessions lost)
```

### 11.2 Document Lifecycle

```mermaid
stateDiagram-v2
    [*] --> OnDisk : user has file on filesystem
    OnDisk --> Processing : ingest_file() called
    Processing --> Parsed : parser.parse() returns segments
    Processing --> Failed : parser raises ValueError/FileNotFoundError
    Parsed --> Chunked : chunk_text() splits into Chunks
    Chunked --> Stored : collection.add() writes to ChromaDB
    Stored --> Searchable : document available to search()
    Searchable --> Stored : another document ingested
    Searchable --> [*] : delete_document(document_id) - removes all chunks from ChromaDB
    Failed --> [*]
```

### 11.3 LLM Provider State (LLMRouter)

```mermaid
stateDiagram-v2
    [*] --> Uncreated : LLMRouter initialized\n(empty cache)
    Uncreated --> Created : get_provider("ollama")\n_build_ollama() called
    Uncreated --> Created : get_provider("openai")\n_build_openai() called
    Uncreated --> Failed : api_key missing\nraises ValueError
    Created --> Cached : stored in _cache dict
    Cached --> Cached : get_provider(name)\nreturned from cache (no rebuild)
    Failed --> [*]
```

---

## 12. Vision-to-Implementation Traceability Matrix

### 12.1 Functional Requirements

| Req ID | Requirement (from Vision.md) | Status | Implementation |
|--------|------------------------------|--------|----------------|
| FR1 | Web-based UI with chat window | 🟡 Deferred | Server exposes REST API + SSE; UI is Phase 2 (intentional — spec says UI deferred) |
| FR2 | Mechanism to ingest a local PDF file | ✅ Done | `POST /api/ingest/upload` (file bytes), `POST /api/ingest/path` (local path), MCP `ingest_document` |
| FR3 | Backend receives user messages from frontend | ✅ Done | `POST /api/chat` (`ChatRequest.message`); MCP `ask_hermes(question)` |
| FR4 | Agent uses RAG tool to search vector DB | ✅ Done | `HermesAgent` + `create_rag_search_tool()` — LangChain tool calls `KnowledgeService.search()` |
| FR5 | Agent calls cloud LLM with question + context | ✅ Done | `LLMRouter` supports OpenAI, Gemini (cloud); Ollama (local); switched per request |
| FR6 | Frontend displays AI response | 🟡 Deferred | `ChatResponse` returned; SSE streaming supported; UI is Phase 2 |

### 12.2 Non-Functional Requirements

| Req ID | Requirement | Status | Implementation |
|--------|-------------|--------|----------------|
| NFR1 | Documents never transmitted outside local machine | ✅ Done | ChromaDB persists locally (`./data/chromadb/`). Cloud LLMs only receive text chunks. No file upload to cloud. |
| NFR2 | Response time < 10s | 🟡 Depends on LLM | Hash embeddings: ~1ms. Chunking 100-page PDF: ~2-3s. LLM response: depends on provider/model. Architecture adds <100ms overhead. |
| NFR3 | Clean, simple, intuitive UI | 🟡 Deferred | Phase 2 |
| NFR4 | Modular backend — separate API, agent logic, tools | ✅ Done | Clear layer separation: `server.py` (transport) → `services/` (orchestration) → `core/` (logic) → `tools/` (tool definitions) → `processing/` (data) |

### 12.3 Extended Requirements (from Phase 0+1 Plan)

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Multi-format ingestion (PDF, TXT, MD, DOCX, Code, Images) | ✅ Done | 6 parsers in `hermes/processing/parsers/` |
| Pluggable LLM providers | ✅ Done | `LLMRouter` — Ollama, OpenAI, Gemini |
| SSE streaming | ✅ Done | `chat_stream()` → `astream_events()` → `StreamingResponse` |
| MCP server for VS Code Copilot | ✅ Done | `hermes/mcp_server.py` — 5 tools |
| Conversation memory | ✅ Done | `ConversationMemory` — in-memory, 20-message window |
| Auth middleware | ✅ Done | `AuthMiddleware` — API key, localhost bypass, disabled by default |
| Config with env var expansion | ✅ Done | `${VAR}` in `config.yaml` replaced from environment |
| OCR for scanned images | ✅ Done | `OCRParser` (requires Tesseract to be installed) |
| Test coverage | ✅ Done | 70 unit + integration tests |

### 12.4 What Exceeded the Original Vision

| Addition | Rationale |
|----------|-----------|
| MCP server (VS Code Copilot) | Not in original Vision but requested pre-implementation |
| Three LLM providers (Ollama + OpenAI + Gemini) | Vision had one; added modularity |
| SSE token streaming | Vision assumed full response; streaming improves UX |
| 6 document types vs 1 (PDF only) | Vision said single PDF; Plan extended this |
| Code file parsing | Added proactively for developer use case |
| Auth middleware | Not in Vision; added for cloud UI access safety |
| 70 automated tests | Vision had informal testing |

---

## 13. Known Gaps & Phase 2 Candidates

| Gap | Severity | Notes |
|-----|----------|-------|
| **Embedding quality** — hash-based embeddings give no real semantic similarity | High | Upgrade to `OllamaEmbeddingFunction("nomic-embed-text")` in `KnowledgeService.__init__` |
| **Conversation sessions not persisted** — lost on restart | Medium | Store sessions in SQLite or ChromaDB metadata |
| **No document metadata store** — `list_documents()` reconstructs from ChromaDB | Medium | Add a lightweight SQLite/JSON document registry |
| **No web UI** (FR1, FR6) | High for end users | Phase 2 — Next.js or React client |
| **No WebSocket support** — only SSE for streaming | Low | SSE is sufficient for unidirectional streaming; WS adds complexity |
| **No rate limiting or abuse protection** | Medium | Add FastAPI middleware or use reverse proxy (nginx) |
| **SingleUser only** — no multi-user session isolation | Low | Personal tool; adequate for PoC |
| **Agent has no tools beyond RAG** | Medium | Phase 2: web search, calendar, file system tool |
| **Ollama connectivity check** — `is_available()` only checks object creation | Low | Add a real ping check to Ollama health endpoint |
| **Upload size limit** — no max file size enforced on `POST /api/ingest/upload` | Medium | Add `UploadFile` size validation |
| **No document deduplication** — ingesting same file twice creates duplicate chunks | Medium | Hash file content on ingest; skip if already stored |

---

## Appendix A — REST API Summary

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/providers` | List LLM providers and availability |
| `POST` | `/api/chat` | Send message; `stream:false` → full response; `stream:true` → SSE |
| `POST` | `/api/ingest/upload` | Ingest multipart file upload |
| `POST` | `/api/ingest/path` | Ingest local file by path |
| `GET` | `/api/documents` | List all ingested documents |
| `DELETE` | `/api/documents/{document_id}` | Remove document from knowledge base |
| `GET` | `/api/sessions/{session_id}` | Get conversation history for session |
| `DELETE` | `/api/sessions/{session_id}` | Delete a session |

## Appendix B — MCP Tools Summary

| Tool | Sync/Async | Description |
|------|-----------|-------------|
| `search_knowledge` | sync | Raw vector search — returns top-k passages, no LLM |
| `ask_hermes` | async | Full RAG pipeline — search + LLM reasoning |
| `ingest_document` | sync | Ingest a file by local path |
| `list_documents` | sync | List all documents in knowledge base |
| `remove_document` | sync | Remove a document by ID |

## Appendix C — Entry Points

```bash
# REST API server (default, for UI clients)
python -m hermes
python -m hermes --host 0.0.0.0 --port 8000 --config /path/to/config.yaml

# MCP server (for VS Code Copilot — spawned by VS Code)
python -m hermes --mcp

# VS Code settings.json MCP entry
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





🧠 **1. CORE GOAL: ARCHITECTING AI AGENTS**
   ┃
   ┣━━🤖 **2. The AI Agent (The Entity)**
   ┃   ┣━ **Definition:** An autonomous system that can perceive, reason, plan, and act to achieve goals.
   ┃   ┗━ **Core Process: The Agentic Loop**
   ┃       ┣━ **Observe:** Gathers information about its environment.
   ┃       ┣━ **Think:** Reasons about a plan to achieve its goal. (This is where the LLM shines).
   ┃       ┣━ **Act:** Executes a plan by using tools (e.g., calling an API, running code, or using RAG).
   ┃       ┗━ **Repeat:** Uses the result of the action to observe again and continue the loop.
   ┃
   ┣━━💡 **3. The LLM (The "Brain")**
   ┃   ┣━ **Role:** The central reasoning and language engine.
   ┃   ┗━ **Inherent Limitations (The "Why"):**
   ┃       ┣━ ❌ **Knowledge Cutoff:** Knowledge is frozen at the time of training.
   ┃       ┗━ ❌ **Hallucination:** Invents plausible but incorrect facts when it doesn't know an answer.
   ┃
   ┣━━📚 **4. Retrieval-Augmented Generation (RAG) (The "External Knowledge")**
   ┃   ┣━ **Purpose:** To solve the LLM's limitations by connecting it to real-time, factual, or private data.
   ┃   ┣━ **Process Flow:**
   ┃   ┃   ┣━ **[A] Retrieval Phase:** Find relevant information.
   ┃   ┃   ┗━ **[B] Generation Phase:** Use that information to generate an answer.
   ┃   ┃
   ┃   ┗━ **Deep Dive: [A] The Retrieval Phase & Vector Search**
   ┃       ┣━ **Goal:** Find data based on semantic meaning, not just keywords.
   ┃       ┃
   ┃       ┣━ **(Offline) Step 1: INDEXING**
   ┃       ┃   ┣━ **Chunking:** Break down large documents into smaller, meaningful pieces.
   ┃       ┃   ┣━ **Embedding:** Use an **Embedding Model** to convert each text chunk into a numerical vector.
   ┃       ┃   ┗━ **Storing:** Store these vectors in a specialized **Vector Database**.
   ┃       ┃
   ┃       ┗━ **(Real-Time) Step 2: QUERYING**
   ┃           ┣━ **Embed Query:** Convert the user's question into a vector with the same model.
   ┃           ┣━ **Vector Similarity Search:** Find the "closest" document vectors to the query vector.
   ┃           ┃   ┣━ **How?** Using **Similarity Metrics** (e.g., Cosine Similarity, Euclidean Distance).
   ┃           ┃   ┗━ **How to make it fast?** Using **Approximate Nearest Neighbor (ANN)** algorithms (e.g., HNSW).
   ┃           ┗━ **Retrieve:** Pull the original text chunks corresponding to the closest vectors.
   ┃
   ┗━━ dirigir **5. Context Engineering (The "Director")**
       ┣━ **Definition:** The discipline of managing all information fed into the LLM's "context window."
       ┗━ **What's in the Context Window?**
           ┣━ **System Prompt:** The agent's identity, rules, and persona.
           ┣━ **User Query:** The immediate question from the user.
           ┣━ **Retrieved Data (from RAG):** The factual information needed to answer the query.
           ┣━ **Chat History:** The memory of the current conversation.
           ┗━ **Tool Definitions:** Descriptions of the tools the agent can use.
