"""Tests for KnowledgeService — ChromaDB vector store operations."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from chromadb.errors import InvalidArgumentError

from hermes.config import reset_config


@pytest.fixture(autouse=True)
def _clean_config():
    """Reset config before each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture()
def tmp_chromadb(tmp_path, monkeypatch):
    """Point vectordb.persist_directory to a temp folder."""
    db_dir = tmp_path / "chromadb"
    db_dir.mkdir()
    monkeypatch.setenv("HERMES_TEST_CHROMA", str(db_dir))

    # Patch config to use temp directory
    from hermes.config import load_config
    import hermes.config as config_module

    cfg = load_config()
    cfg.vectordb.persist_directory = str(db_dir)
    config_module._config = cfg

    return db_dir


@pytest.fixture()
def knowledge_svc(tmp_chromadb):
    from hermes.services.knowledge_service import KnowledgeService
    return KnowledgeService()


@pytest.fixture()
def sample_txt(tmp_path):
    """Create a sample text file for ingestion."""
    f = tmp_path / "sample.txt"
    f.write_text(
        "Hermes is a local-first AI knowledge agent. "
        "It processes documents and answers questions using RAG. "
        "The system supports PDF, TXT, Markdown, DOCX, and code files. "
        "All data stays on the user machine for maximum privacy.",
        encoding="utf-8",
    )
    return f


@pytest.fixture()
def sample_md(tmp_path):
    """Create a sample markdown file."""
    f = tmp_path / "guide.md"
    f.write_text(
        "# Getting Started\n\n"
        "Install Hermes using pip install hermes.\n\n"
        "# Configuration\n\n"
        "Edit config.yaml to set your LLM provider.\n"
        "Supported providers: Ollama, OpenAI, Gemini.\n",
        encoding="utf-8",
    )
    return f


class TestIngestion:
    def test_ingest_text_file(self, knowledge_svc, sample_txt):
        result = knowledge_svc.ingest_file(sample_txt)
        assert result.document_id
        assert result.document_name == "sample.txt"
        assert result.chunks_created > 0
        assert result.processing_time_seconds >= 0

    def test_ingest_increases_chunk_count(self, knowledge_svc, sample_txt):
        before = knowledge_svc.total_chunks
        knowledge_svc.ingest_file(sample_txt)
        assert knowledge_svc.total_chunks > before

    def test_ingest_nonexistent_file_raises(self, knowledge_svc, tmp_path):
        with pytest.raises(FileNotFoundError):
            knowledge_svc.ingest_file(tmp_path / "nope.txt")

    def test_ingest_dimension_mismatch_raises_value_error(self, knowledge_svc, sample_txt):
        class _BrokenCollection:
            def add(self, *args, **kwargs):
                raise InvalidArgumentError("Collection expecting embedding with dimension of 384, got 1536")

        knowledge_svc._collection = _BrokenCollection()  # type: ignore[attr-defined]

        with pytest.raises(ValueError, match="Embedding dimension mismatch"):
            knowledge_svc.ingest_file(sample_txt)


class TestSearch:
    def test_search_empty_returns_empty(self, knowledge_svc):
        results = knowledge_svc.search("anything")
        assert results == []

    def test_search_returns_results(self, knowledge_svc, sample_txt):
        knowledge_svc.ingest_file(sample_txt)
        results = knowledge_svc.search("knowledge agent privacy")
        assert len(results) > 0
        assert results[0].text
        assert results[0].document_name == "sample.txt"
        assert 0.0 <= results[0].score <= 1.0

    def test_search_respects_top_k(self, knowledge_svc, sample_txt, sample_md):
        knowledge_svc.ingest_file(sample_txt)
        knowledge_svc.ingest_file(sample_md)
        results = knowledge_svc.search("hermes", top_k=1)
        assert len(results) == 1


class TestDocumentManagement:
    def test_list_documents_empty(self, knowledge_svc):
        docs = knowledge_svc.list_documents()
        assert docs == []

    def test_list_documents_after_ingest(self, knowledge_svc, sample_txt):
        knowledge_svc.ingest_file(sample_txt)
        docs = knowledge_svc.list_documents()
        assert len(docs) == 1
        assert docs[0].name == "sample.txt"
        assert docs[0].chunks_count > 0

    def test_get_document(self, knowledge_svc, sample_txt):
        result = knowledge_svc.ingest_file(sample_txt)
        doc = knowledge_svc.get_document(result.document_id)
        assert doc is not None
        assert doc.name == "sample.txt"

    def test_get_document_not_found(self, knowledge_svc):
        doc = knowledge_svc.get_document("nonexistent")
        assert doc is None

    def test_delete_document(self, knowledge_svc, sample_txt):
        result = knowledge_svc.ingest_file(sample_txt)
        assert knowledge_svc.total_chunks > 0

        deleted = knowledge_svc.delete_document(result.document_id)
        assert deleted is True
        assert knowledge_svc.total_chunks == 0

    def test_delete_nonexistent_returns_false(self, knowledge_svc):
        deleted = knowledge_svc.delete_document("nonexistent")
        assert deleted is False

    def test_multiple_documents(self, knowledge_svc, sample_txt, sample_md):
        knowledge_svc.ingest_file(sample_txt)
        knowledge_svc.ingest_file(sample_md)
        docs = knowledge_svc.list_documents()
        assert len(docs) == 2
        names = {d.name for d in docs}
        assert names == {"sample.txt", "guide.md"}
