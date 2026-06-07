"""Hermes MCP Server — exposes knowledge tools to VS Code Copilot via stdio."""

from __future__ import annotations

import asyncio

from mcp.server import FastMCP

from hermes.config import get_config
from hermes.core.llm_router import LLMRouter
from hermes.core.memory import ConversationMemory
from hermes.log_setup import get_logger, setup_logging
from hermes.services.chat_service import ChatService
from hermes.services.knowledge_service import KnowledgeService

logger = get_logger("mcp")

# ── Service singletons (initialized on first use) ─────────────────

_knowledge: KnowledgeService | None = None
_chat_service: ChatService | None = None


def _init_services() -> tuple[KnowledgeService, ChatService]:
    global _knowledge, _chat_service
    if _knowledge is None:
        llm_router = LLMRouter()
        _knowledge = KnowledgeService(embedding_fn=llm_router.get_embedding_fn())
        memory = ConversationMemory()
        _chat_service = ChatService(_knowledge, llm_router, memory)
        logger.info("MCP services initialized")
    return _knowledge, _chat_service


# ── MCP Server ─────────────────────────────────────────────────────

mcp = FastMCP(
    name="hermes",
    instructions=(
        "Hermes is a local-first AI knowledge agent. "
        "Use its tools to search, query, and manage a personal document knowledge base."
    ),
)


@mcp.tool()
def search_knowledge(query: str, top_k: int = 5) -> str:
    """Search the local knowledge base for information relevant to the query.

    Returns the most relevant text passages from ingested documents.
    """
    knowledge, _ = _init_services()
    results = knowledge.search(query, top_k=top_k)

    if not results:
        return "No relevant documents found in the knowledge base."

    parts: list[str] = []
    for i, r in enumerate(results, 1):
        parts.append(f"[{i}] (Source: {r.document_name}, score: {r.score})\n{r.text}")
    return "\n\n---\n\n".join(parts)


@mcp.tool()
async def ask_hermes(question: str, provider: str = "") -> str:
    """Ask a question about your local documents using the full RAG pipeline.

    Uses retrieval-augmented generation to find relevant context and generate
    an answer. Optionally specify an LLM provider (ollama, openai, gemini).
    """
    _, chat_service = _init_services()
    response = await chat_service.chat(
        message=question,
        provider=provider or None,
    )
    return response.answer


@mcp.tool()
def ingest_document(file_path: str) -> str:
    """Add a document to the knowledge base.

    Supports: PDF, TXT, Markdown, DOCX, code files (.py, .js, .ts, etc.),
    and images (PNG, JPG — requires Tesseract OCR).
    """
    knowledge, _ = _init_services()
    try:
        result = knowledge.ingest_file(file_path)
        return (
            f"Successfully ingested '{result.document_name}'\n"
            f"  Document ID: {result.document_id}\n"
            f"  Type: {result.doc_type.value}\n"
            f"  Chunks created: {result.chunks_created}\n"
            f"  Processing time: {result.processing_time_seconds:.2f}s"
        )
    except FileNotFoundError:
        return f"Error: File not found — {file_path}"
    except ValueError as exc:
        return f"Error: {exc}"


@mcp.tool()
def list_documents() -> str:
    """List all documents in the knowledge base with their names and IDs."""
    knowledge, _ = _init_services()
    docs = knowledge.list_documents()

    if not docs:
        return "The knowledge base is empty. Use ingest_document to add files."

    lines = [f"Knowledge base: {len(docs)} document(s)\n"]
    for i, d in enumerate(docs, 1):
        lines.append(
            f"  [{i}] Name : {d.name}\n"
            f"       ID   : {d.document_id}\n"
            f"       Type : {d.doc_type.value}  |  Chunks: {d.chunks_count}  |  Ingested: {d.ingested_at.strftime('%Y-%m-%d %H:%M')}"
        )
    return "\n".join(lines)


@mcp.tool()
def remove_document(document_id: str) -> str:
    """Remove a document from the knowledge base by its ID."""
    knowledge, _ = _init_services()
    deleted = knowledge.delete_document(document_id)
    if deleted:
        return f"Document {document_id} removed from the knowledge base."
    return f"Document {document_id} not found in the knowledge base."


# ── Entry point ────────────────────────────────────────────────────


def run_mcp_server() -> None:
    """Run the MCP server over stdio (called from __main__.py --mcp)."""
    setup_logging()
    logger.info("Starting Hermes MCP server (stdio)")
    mcp.run(transport="stdio")
