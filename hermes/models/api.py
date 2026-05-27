"""Pydantic models for API requests and responses."""

from __future__ import annotations

from typing import Any

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
    reachable: bool | None = None
    latency_ms: int | None = None
    api_key_set: bool = False
    model: str | None = None


class ProvidersResponse(BaseModel):
    default: str
    providers: list[ProviderInfo]


# --- Config ---

class ProviderConfigPatch(BaseModel):
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    deployment: str | None = None
    api_version: str | None = None
    embedding_deployment: str | None = None
    embedding_model: str | None = None


class ConfigPatchRequest(BaseModel):
    default_provider: str | None = None
    embedding_provider: str | None = None
    providers: dict[str, ProviderConfigPatch] | None = None


class ConfigResponse(BaseModel):
    default_provider: str
    embedding_provider: str
    providers: dict[str, Any]


# --- Sessions ---

class MessageInfo(BaseModel):
    role: str
    content: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageInfo]
