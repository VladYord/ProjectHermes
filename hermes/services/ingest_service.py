"""Ingest service — orchestrates document ingestion."""

from __future__ import annotations

from pathlib import Path

from hermes.log_setup import get_logger
from hermes.models.domain import IngestResult
from hermes.services.knowledge_service import KnowledgeService

logger = get_logger("ingest")


class IngestService:
    """Thin orchestration layer for document ingestion."""

    def __init__(self, knowledge: KnowledgeService) -> None:
        self._knowledge = knowledge

    def ingest_file(self, file_path: str | Path, document_name: str | None = None) -> IngestResult:
        """Ingest a file into the knowledge base."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return self._knowledge.ingest_file(path, document_name=document_name)

