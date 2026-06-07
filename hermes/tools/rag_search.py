"""RAG search tool — LangChain tool wrapper around the knowledge service."""

from __future__ import annotations

from langchain_core.tools import tool

from hermes.log_setup import get_logger
from hermes.services.knowledge_service import KnowledgeService

logger = get_logger("rag_tool")


def create_rag_search_tool(knowledge: KnowledgeService):
    """Create a LangChain tool that searches the knowledge base.

    This is a factory function — the tool closes over the knowledge service instance.
    """

    @tool
    def search_knowledge_base(query: str, top_k: int = 5) -> str:
        """Search the local knowledge base for information relevant to the query.

        Returns the most relevant text passages from ingested documents,
        along with source attribution.
        """
        results = knowledge.search(query, top_k=top_k)

        if not results:
            return "No relevant documents found in the knowledge base."

        parts: list[str] = []
        for i, r in enumerate(results, 1):
            parts.append(
                f"[{i}] (Source: {r.document_name}, score: {r.score})\n{r.text}"
            )

        return "\n\n---\n\n".join(parts)

    return search_knowledge_base
