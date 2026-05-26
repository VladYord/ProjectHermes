"""Pydantic models for API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Chat ---

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    provider: str | None = None
    stream: bool = False


class SourceInfo(BaseModel):
    document: str
    chunk: str
    score: float = 0.0


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[SourceInfo] = Field(default_factory=list)


# --- Ingestion ---

class IngestByPathRequest(BaseModel):
    file_path: str


class IngestResponse(BaseModel):
    status: str = "success"
    document_id: str
    document_name: str
    chunks_created: int
    processing_time_seconds: float


# --- Documents ---

class DocumentInfo(BaseModel):
    document_id: str
    name: str
    doc_type: str
    chunks_count: int
    ingested_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]


# --- System ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class ProviderInfo(BaseModel):
    name: str
    available: bool


class ProvidersResponse(BaseModel):
    default: str
    providers: list[ProviderInfo]


# --- Sessions ---

class MessageInfo(BaseModel):
    role: str
    content: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageInfo]
