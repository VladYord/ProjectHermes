"""Chat service — orchestrates agent, LLM, tools, and memory."""

from __future__ import annotations

from collections.abc import AsyncIterator

from hermes.core.agent import HermesAgent
from hermes.core.llm_router import LLMRouter
from hermes.core.memory import ConversationMemory
from hermes.log_setup import get_logger
from hermes.models.domain import ChatResponse
from hermes.services.knowledge_service import KnowledgeService
from hermes.tools.rag_search import create_rag_search_tool

logger = get_logger("chat")


class ChatService:
    """High-level service that creates agents on demand and routes chat requests."""

    def __init__(
        self,
        knowledge: KnowledgeService,
        llm_router: LLMRouter,
        memory: ConversationMemory,
    ) -> None:
        self._knowledge = knowledge
        self._llm_router = llm_router
        self._memory = memory
        self._agents: dict[str, HermesAgent] = {}  # keyed by provider name

    def _get_agent(self, provider: str | None = None) -> HermesAgent:
        """Get or create an agent for the given provider."""
        provider_name = provider or "default"

        if provider_name not in self._agents:
            llm = (
                self._llm_router.get_provider(provider)
                if provider
                else self._llm_router.get_default()
            )
            rag_tool = create_rag_search_tool(self._knowledge)

            self._agents[provider_name] = HermesAgent(
                llm=llm,
                tools=[rag_tool],
                memory=self._memory,
            )
            logger.info("Created agent for provider: %s", provider_name)

        return self._agents[provider_name]

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        provider: str | None = None,
    ) -> ChatResponse:
        """Process a chat message through the agent pipeline."""
        agent = self._get_agent(provider)
        return await agent.chat(message, session_id=session_id)

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
        provider: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream a chat response token by token."""
        agent = self._get_agent(provider)
        async for token in agent.chat_stream(message, session_id=session_id):
            yield token
