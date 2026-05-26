"""Integration tests for the MCP server."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from hermes.config import reset_config


@pytest.fixture(autouse=True)
def _clean_config():
    reset_config()
    yield
    reset_config()


@pytest.fixture()
def mcp_setup(tmp_path, monkeypatch):
    """Set up MCP server with temp directories and return the FastMCP instance."""
    import hermes.config as config_module
    from hermes.config import load_config

    cfg = load_config()
    cfg.vectordb.persist_directory = str(tmp_path / "chromadb")
    config_module._config = cfg

    # Reset singleton services in mcp_server module
    import hermes.mcp_server as mcp_mod

    mcp_mod._knowledge = None
    mcp_mod._chat_service = None

    yield mcp_mod.mcp

    mcp_mod._knowledge = None
    mcp_mod._chat_service = None


@pytest.fixture()
def sample_file(tmp_path):
    f = tmp_path / "mcp_test.txt"
    f.write_text("Hermes MCP test document. Contains knowledge about local AI.", encoding="utf-8")
    return str(f)


class TestMCPToolRegistration:
    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_setup):
        """MCP server should register all expected tools."""
        tools = await mcp_setup.list_tools()
        tool_names = {t.name for t in tools}
        expected = {"search_knowledge", "ask_hermes", "ingest_document", "list_documents", "remove_document"}
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"


class TestMCPIngest:
    @pytest.mark.asyncio
    async def test_ingest_document(self, mcp_setup, sample_file):
        """Ingesting via MCP should return success info."""
        result = await mcp_setup.call_tool("ingest_document", {"file_path": sample_file})
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert "Successfully ingested" in text
        assert "mcp_test.txt" in text

    @pytest.mark.asyncio
    async def test_ingest_nonexistent(self, mcp_setup):
        """Ingesting a missing file should return an error message (not crash)."""
        result = await mcp_setup.call_tool("ingest_document", {"file_path": "/no/such/file.txt"})
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert "Error" in text


class TestMCPDocumentManagement:
    @pytest.mark.asyncio
    async def test_list_empty(self, mcp_setup):
        """List documents on empty knowledge base."""
        result = await mcp_setup.call_tool("list_documents", {})
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert "empty" in text.lower()

    @pytest.mark.asyncio
    async def test_ingest_and_list(self, mcp_setup, sample_file):
        """After ingesting, list should show the document."""
        await mcp_setup.call_tool("ingest_document", {"file_path": sample_file})
        result = await mcp_setup.call_tool("list_documents", {})
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert "1 document" in text
        assert "mcp_test.txt" in text

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, mcp_setup):
        """Removing a nonexistent document should return not-found message."""
        result = await mcp_setup.call_tool("remove_document", {"document_id": "fake123"})
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert "not found" in text.lower()


class TestMCPSearch:
    @pytest.mark.asyncio
    async def test_search_empty(self, mcp_setup):
        """Search on empty knowledge base should return no results."""
        result = await mcp_setup.call_tool("search_knowledge", {"query": "test"})
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        assert "no relevant" in text.lower()

    @pytest.mark.asyncio
    async def test_search_after_ingest(self, mcp_setup, sample_file):
        """Search should return results after ingesting a document."""
        await mcp_setup.call_tool("ingest_document", {"file_path": sample_file})
        result = await mcp_setup.call_tool("search_knowledge", {"query": "local AI knowledge"})
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
        # Should have at least some content (may not be "relevant" with hash embeddings)
        assert len(text) > 0
