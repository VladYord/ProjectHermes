"""Hermes REST API Server — FastAPI application."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from hermes import __version__
from hermes.config import get_config
from hermes.config_manager import (
    HermesAppConfig,
    load_app_config,
    merge_into_config,
    save_app_config,
)
from hermes.core.llm_router import LLMRouter
from hermes.core.memory import ConversationMemory
from hermes.logging import get_logger
from hermes.middleware.auth import AuthMiddleware
from hermes.models import api as schemas
from hermes.services.chat_service import ChatService
from hermes.services.ingest_service import IngestService
from hermes.services.knowledge_service import KnowledgeService

logger = get_logger("server")

# --- Shared state (initialized at startup) ---
_knowledge: KnowledgeService | None = None
_llm_router: LLMRouter | None = None
_memory: ConversationMemory | None = None
_chat_service: ChatService | None = None
_ingest_service: IngestService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and clean up on shutdown."""
    global _knowledge, _llm_router, _memory, _chat_service, _ingest_service

    logger.info("Starting Hermes server v%s", __version__)

    # Overlay API keys from encrypted config.enc onto the runtime config.
    try:
        merge_into_config(get_config(), load_app_config())
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load encrypted app config: %s", exc)

    _llm_router = LLMRouter()
    _knowledge = KnowledgeService(embedding_fn=_llm_router.get_embedding_fn())
    _memory = ConversationMemory()
    _chat_service = ChatService(_knowledge, _llm_router, _memory)
    _ingest_service = IngestService(_knowledge)
    logger.info("All services initialized")

    yield

    logger.info("Hermes server shutting down")


app = FastAPI(
    title="Hermes",
    description="Local-first AI knowledge agent",
    version=__version__,
    lifespan=lifespan,
)

# CORS — specific origins for Tauri WebView and Vite dev server.
# allow_credentials=True is incompatible with allow_origins=["*"].
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",        # Tauri WebView (production bundle)
        "https://tauri.localhost",  # Tauri WebView variant
        "http://localhost:5173",    # Vite dev server
        "http://localhost:1420",    # Tauri dev fallback
        "http://127.0.0.1:5173",
        "http://localhost:8000",    # Direct backend calls
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware
app.add_middleware(AuthMiddleware)


# ── Helpers ──────────────────────────────────────────────────────


def _require(service, name: str):
    if service is None:
        raise HTTPException(status_code=503, detail=f"{name} not initialized")
    return service


# ── System Endpoints ─────────────────────────────────────────────


@app.get("/api/health", response_model=schemas.HealthResponse)
async def health():
    return schemas.HealthResponse(version=__version__)


@app.get("/api/providers", response_model=schemas.ProvidersResponse)
async def list_providers():
    router = _require(_llm_router, "LLM Router")
    cfg = get_config()
    llm_cfg = cfg.llm
    providers_cfg = llm_cfg.providers

    # Run Ollama connectivity check concurrently with building the provider list.
    ollama_reachable: bool | None = None
    ollama_latency: int | None = None
    try:
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{providers_cfg.ollama.base_url}/api/tags")
        ollama_reachable = resp.status_code == 200
        ollama_latency = int((time.monotonic() - t0) * 1000)
    except Exception:
        ollama_reachable = False

    def _make_provider(name: str) -> schemas.ProviderInfo:
        match name:
            case "ollama":
                return schemas.ProviderInfo(
                    name=name,
                    available=True,
                    reachable=ollama_reachable,
                    latency_ms=ollama_latency,
                    api_key_set=False,
                    model=providers_cfg.ollama.model,
                )
            case "openai":
                key_set = bool(providers_cfg.openai.api_key)
                return schemas.ProviderInfo(
                    name=name,
                    available=key_set,
                    reachable=key_set or None,
                    api_key_set=key_set,
                    model=providers_cfg.openai.model,
                )
            case "gemini":
                key_set = bool(providers_cfg.gemini.api_key)
                return schemas.ProviderInfo(
                    name=name,
                    available=key_set,
                    reachable=key_set or None,
                    api_key_set=key_set,
                    model=providers_cfg.gemini.model,
                )
            case "azure_openai":
                key_set = bool(providers_cfg.azure_openai.api_key)
                return schemas.ProviderInfo(
                    name=name,
                    available=key_set,
                    reachable=key_set or None,
                    api_key_set=key_set,
                    model=providers_cfg.azure_openai.deployment,
                )
            case _:
                return schemas.ProviderInfo(
                    name=name,
                    available=router.is_available(name),
                )

    providers = [_make_provider(name) for name in router.list_providers()]
    return schemas.ProvidersResponse(default=llm_cfg.default_provider, providers=providers)


@app.get("/api/config", response_model=schemas.ConfigResponse)
async def get_config_endpoint():
    """Return current configuration with API keys masked."""
    cfg = get_config()
    p = cfg.llm.providers
    return schemas.ConfigResponse(
        default_provider=cfg.llm.default_provider,
        embedding_provider=cfg.vectordb.embedding_provider,
        providers={
            "ollama": {
                "base_url": p.ollama.base_url,
                "model": p.ollama.model,
                "embedding_model": p.ollama.embedding_model,
            },
            "openai": {
                "model": p.openai.model,
                "api_key_set": bool(p.openai.api_key),
            },
            "gemini": {
                "model": p.gemini.model,
                "api_key_set": bool(p.gemini.api_key),
            },
            "azure_openai": {
                "base_url": p.azure_openai.base_url,
                "deployment": p.azure_openai.deployment,
                "api_version": p.azure_openai.api_version,
                "embedding_deployment": p.azure_openai.embedding_deployment,
                "api_key_set": bool(p.azure_openai.api_key),
            },
        },
    )


@app.patch("/api/config", response_model=schemas.ConfigResponse)
async def patch_config(request: schemas.ConfigPatchRequest):
    """Update config settings.  API keys are encrypted before storage."""
    cfg = get_config()
    app_cfg = load_app_config()

    if request.default_provider is not None:
        cfg.llm.default_provider = request.default_provider
        app_cfg.default_provider = request.default_provider

    if request.embedding_provider is not None:
        cfg.vectordb.embedding_provider = request.embedding_provider
        app_cfg.embedding_provider = request.embedding_provider

    if request.providers:
        p = cfg.llm.providers
        for provider_name, patch in request.providers.items():
            match provider_name:
                case "openai":
                    if patch.api_key is not None:
                        p.openai.api_key = patch.api_key
                        app_cfg.openai_api_key = patch.api_key
                    if patch.model is not None:
                        p.openai.model = patch.model
                        app_cfg.openai_model = patch.model
                case "gemini":
                    if patch.api_key is not None:
                        p.gemini.api_key = patch.api_key
                        app_cfg.gemini_api_key = patch.api_key
                    if patch.model is not None:
                        p.gemini.model = patch.model
                        app_cfg.gemini_model = patch.model
                case "azure_openai":
                    if patch.api_key is not None:
                        p.azure_openai.api_key = patch.api_key
                        app_cfg.azure_openai_api_key = patch.api_key
                    if patch.base_url is not None:
                        p.azure_openai.base_url = patch.base_url
                        app_cfg.azure_openai_base_url = patch.base_url
                    if patch.deployment is not None:
                        p.azure_openai.deployment = patch.deployment
                        app_cfg.azure_openai_deployment = patch.deployment
                case "ollama":
                    if patch.base_url is not None:
                        p.ollama.base_url = patch.base_url
                        app_cfg.ollama_base_url = patch.base_url
                    if patch.model is not None:
                        p.ollama.model = patch.model
                        app_cfg.ollama_model = patch.model
                    if patch.embedding_model is not None:
                        p.ollama.embedding_model = patch.embedding_model
                        app_cfg.ollama_embedding_model = patch.embedding_model

    # Persist to encrypted file and clear provider cache so new keys take effect.
    save_app_config(app_cfg)
    if _llm_router is not None:
        _llm_router._cache.clear()
        _llm_router._embedding_cache.clear()

    return await get_config_endpoint()


# ── Chat ─────────────────────────────────────────────────────────


@app.post("/api/chat")
async def chat(request: schemas.ChatRequest):
    svc = _require(_chat_service, "Chat Service")

    if request.stream:
        return _stream_chat(svc, request)

    try:
        result = await svc.chat(
            message=request.message,
            session_id=request.session_id,
            provider=request.provider,
        )
        return schemas.ChatResponse(
            session_id=result.session_id,
            answer=result.answer,
            sources=[
                schemas.SourceInfo(
                    document=s.document_name,
                    chunk=s.text[:200],
                    score=s.score,
                )
                for s in result.sources
            ],
        )
    except Exception as exc:
        logger.error("Chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


def _stream_chat(svc, request: schemas.ChatRequest) -> StreamingResponse:
    """Return an SSE streaming response for chat."""

    async def event_generator():
        try:
            async for token in svc.chat_stream(
                message=request.message,
                session_id=request.session_id,
                provider=request.provider,
            ):
                data = json.dumps({"token": token})
                yield f"data: {data}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            logger.error("Stream error: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Ingestion ────────────────────────────────────────────────────


@app.post("/api/ingest", response_model=schemas.IngestResponse)
async def ingest_by_path(request: schemas.IngestByPathRequest):
    """Ingest a document by file path."""
    svc = _require(_ingest_service, "Ingest Service")

    try:
        result = svc.ingest_file(request.file_path)
        return schemas.IngestResponse(
            document_id=result.document_id,
            document_name=result.document_name,
            chunks_created=result.chunks_created,
            processing_time_seconds=result.processing_time_seconds,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/ingest/upload", response_model=schemas.IngestResponse)
async def ingest_upload(file: UploadFile = File(...)):
    """Ingest a document by uploading it."""
    svc = _require(_ingest_service, "Ingest Service")

    import tempfile

    suffix = Path(file.filename or "upload.txt").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = svc.ingest_file(tmp_path, document_name=file.filename or None)
        return schemas.IngestResponse(
            document_id=result.document_id,
            document_name=result.document_name,
            chunks_created=result.chunks_created,
            processing_time_seconds=result.processing_time_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── Documents ────────────────────────────────────────────────────


@app.get("/api/documents", response_model=schemas.DocumentListResponse)
async def list_documents():
    knowledge = _require(_knowledge, "Knowledge Service")
    docs = knowledge.list_documents()
    return schemas.DocumentListResponse(
        documents=[
            schemas.DocumentInfo(
                document_id=d.document_id,
                name=d.name,
                doc_type=d.doc_type.value,
                chunks_count=d.chunks_count,
                ingested_at=d.ingested_at.isoformat(),
            )
            for d in docs
        ]
    )


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    knowledge = _require(_knowledge, "Knowledge Service")
    doc = knowledge.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return schemas.DocumentInfo(
        document_id=doc.document_id,
        name=doc.name,
        doc_type=doc.doc_type.value,
        chunks_count=doc.chunks_count,
        ingested_at=doc.ingested_at.isoformat(),
    )


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    knowledge = _require(_knowledge, "Knowledge Service")
    deleted = knowledge.delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"status": "deleted", "document_id": document_id}


# ── Sessions ─────────────────────────────────────────────────────


@app.get("/api/sessions")
async def list_sessions():
    mem = _require(_memory, "Memory")
    return {"sessions": mem.list_sessions()}


@app.get("/api/sessions/{session_id}/history", response_model=schemas.SessionHistoryResponse)
async def get_session_history(session_id: str):
    mem = _require(_memory, "Memory")
    session = mem.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return schemas.SessionHistoryResponse(
        session_id=session_id,
        messages=[
            schemas.MessageInfo(role=m.role, content=m.content)
            for m in session.messages
        ],
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    mem = _require(_memory, "Memory")
    deleted = mem.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}
