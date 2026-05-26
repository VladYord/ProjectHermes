"""Domain models for Hermes."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime


class DocumentType(enum.Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"
    CODE = "code"
    IMAGE = "image"  # For OCR


@dataclass
class Chunk:
    """A text chunk produced by the document processing pipeline."""

    text: str
    metadata: dict[str, str | int | float] = field(default_factory=dict)


@dataclass
class IngestResult:
    """Result returned after ingesting a document."""

    document_id: str
    document_name: str
    doc_type: DocumentType
    chunks_created: int
    processing_time_seconds: float


@dataclass
class DocumentRecord:
    """Metadata record for an ingested document."""

    document_id: str
    name: str
    file_path: str
    doc_type: DocumentType
    chunks_count: int
    ingested_at: datetime = field(default_factory=datetime.now)


@dataclass
class SearchResult:
    """A single search result from the knowledge base."""

    text: str
    document_name: str
    score: float
    metadata: dict[str, str | int | float] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """Response from the agent chat pipeline."""

    answer: str
    session_id: str
    sources: list[SearchResult] = field(default_factory=list)
