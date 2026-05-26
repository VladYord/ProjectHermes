"""Hermes REST API Server — FastAPI application."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

from hermes import __version__
from hermes.config import get_config
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

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    cfg = get_config().llm
    providers = [
        schemas.ProviderInfo(name=name, available=router.is_available(name))
        for name in router.list_providers()
    ]
    return schemas.ProvidersResponse(default=cfg.default_provider, providers=providers)


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
