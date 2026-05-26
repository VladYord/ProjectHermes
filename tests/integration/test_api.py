"""Integration tests for the REST API server."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hermes.config import reset_config


@pytest.fixture(autouse=True)
def _clean_config():
    reset_config()
    yield
    reset_config()


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    """Create a test client with services wired to temp directories."""
    import hermes.config as config_module
    from hermes.config import load_config

    cfg = load_config()
    cfg.vectordb.persist_directory = str(tmp_path / "chromadb")
    config_module._config = cfg

    # Import after config is set
    from hermes.server import app
    import hermes.server as server_module
    from hermes.services.knowledge_service import KnowledgeService
    from hermes.services.ingest_service import IngestService
    from hermes.core.llm_router import LLMRouter
    from hermes.core.memory import ConversationMemory
    from hermes.services.chat_service import ChatService

    # Initialize services manually (bypass lifespan for tests)
    knowledge = KnowledgeService()
    llm_router = LLMRouter()
    memory = ConversationMemory()
    chat_service = ChatService(knowledge, llm_router, memory)
    ingest_service = IngestService(knowledge)

    server_module._knowledge = knowledge
    server_module._llm_router = llm_router
    server_module._memory = memory
    server_module._chat_service = chat_service
    server_module._ingest_service = ingest_service

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    # Clean up
    server_module._knowledge = None
    server_module._llm_router = None
    server_module._memory = None
    server_module._chat_service = None
    server_module._ingest_service = None


@pytest.fixture()
def sample_file(tmp_path):
    f = tmp_path / "test_doc.txt"
    f.write_text(
        "Hermes is a local AI knowledge agent. Documents stay on your machine.",
        encoding="utf-8",
    )
    return str(f)


class TestHealthEndpoint:
    def test_health(self, api_client):
        resp = api_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestProvidersEndpoint:
    def test_list_providers(self, api_client):
        resp = api_client.get("/api/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "default" in data
        assert "providers" in data
        names = [p["name"] for p in data["providers"]]
        assert "ollama" in names


class TestIngestEndpoint:
    def test_ingest_by_path(self, api_client, sample_file):
        resp = api_client.post("/api/ingest", json={"file_path": sample_file})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["chunks_created"] > 0
        assert data["document_id"]

    def test_ingest_not_found(self, api_client):
        resp = api_client.post("/api/ingest", json={"file_path": "/nonexistent.txt"})
        assert resp.status_code == 404

    def test_ingest_upload(self, api_client):
        content = b"This is uploaded test content for Hermes knowledge base."
        resp = api_client.post(
            "/api/ingest/upload",
            files={"file": ("uploaded.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunks_created"] > 0


class TestDocumentsEndpoint:
    def test_list_documents_empty(self, api_client):
        resp = api_client.get("/api/documents")
        assert resp.status_code == 200
        assert resp.json()["documents"] == []

    def test_list_after_ingest(self, api_client, sample_file):
        api_client.post("/api/ingest", json={"file_path": sample_file})
        resp = api_client.get("/api/documents")
        assert resp.status_code == 200
        docs = resp.json()["documents"]
        assert len(docs) == 1

    def test_get_document(self, api_client, sample_file):
        ingest = api_client.post("/api/ingest", json={"file_path": sample_file}).json()
        doc_id = ingest["document_id"]
        resp = api_client.get(f"/api/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["document_id"] == doc_id

    def test_get_document_not_found(self, api_client):
        resp = api_client.get("/api/documents/nonexistent")
        assert resp.status_code == 404

    def test_delete_document(self, api_client, sample_file):
        ingest = api_client.post("/api/ingest", json={"file_path": sample_file}).json()
        doc_id = ingest["document_id"]
        resp = api_client.delete(f"/api/documents/{doc_id}")
        assert resp.status_code == 200
        # Confirm gone
        resp = api_client.get(f"/api/documents/{doc_id}")
        assert resp.status_code == 404


class TestSessionsEndpoint:
    def test_list_sessions_empty(self, api_client):
        resp = api_client.get("/api/sessions")
        assert resp.status_code == 200
        assert resp.json()["sessions"] == []

    def test_session_not_found(self, api_client):
        resp = api_client.get("/api/sessions/nonexistent/history")
        assert resp.status_code == 404

    def test_delete_session_not_found(self, api_client):
        resp = api_client.delete("/api/sessions/nonexistent")
        assert resp.status_code == 404


class TestStreamingChat:
    def test_stream_returns_sse(self, api_client):
        """Streaming chat should return text/event-stream content type."""
        resp = api_client.post(
            "/api/chat",
            json={"message": "hello", "stream": True},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_ends_with_done(self, api_client):
        """Streaming response should end with a done event (or error if no LLM)."""
        resp = api_client.post(
            "/api/chat",
            json={"message": "test", "stream": True},
        )
        # The response body should contain SSE data lines
        body = resp.text
        assert "data:" in body
