"""Agent engine — LangChain agent with RAG tools and conversation memory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain.agents import create_agent

from hermes.core.memory import ConversationMemory, Session
from hermes.log_setup import get_logger
from hermes.models.domain import ChatResponse

logger = get_logger("agent")

_SYSTEM_PROMPT = (
    "You are Hermes, a helpful AI knowledge assistant. "
    "You answer questions based on the user's local document collection. "
    "When answering, always search the knowledge base first using your tools. "
    "Cite your sources when possible. "
    "If you cannot find relevant information, say so honestly."
)


class HermesAgent:
    """Orchestrates the LLM agent with tools and conversation context."""

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool | Callable[..., Any]],
        memory: ConversationMemory,
    ) -> None:
        self._memory = memory
        self._graph = create_agent(
            model=llm,
            tools=list(tools),
            system_prompt=_SYSTEM_PROMPT,
        )

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
    ) -> ChatResponse:
        """Send a message to the agent and get a response."""
        session = self._memory.get_or_create_session(session_id)

        # Build messages: history + current message
        messages = _session_to_messages(session)
        messages.append(HumanMessage(content=message))

        result = await self._graph.ainvoke({"messages": messages})

        # Extract final AI message from result
        output_messages = result.get("messages", [])
        answer = ""
        for msg in reversed(output_messages):
            if isinstance(msg, AIMessage) and msg.content:
                answer = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        # Save to session
        session.add("human", message)
        session.add("ai", answer)

        return ChatResponse(
            answer=answer,
            session_id=session.session_id,
            sources=[],
        )

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream the agent's response token by token.

        Yields text chunks as they arrive from the LLM.
        After the stream ends, the full response is saved to session history.
        """
        session = self._memory.get_or_create_session(session_id)

        messages = _session_to_messages(session)
        messages.append(HumanMessage(content=message))

        full_answer = ""
        async for event in self._graph.astream_events(
            {"messages": messages}, version="v2"
        ):
            kind = event.get("event", "")
            # Capture streamed tokens from the chat model
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    token = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    full_answer += token
                    yield token

        # Some providers may not surface token-stream events through this path.
        # Fall back to a normal invoke so chat still returns a response.
        if full_answer.strip() == "":
            result = await self._graph.ainvoke({"messages": messages})
            output_messages = result.get("messages", [])
            for msg in reversed(output_messages):
                if isinstance(msg, AIMessage) and msg.content:
                    full_answer = msg.content if isinstance(msg.content, str) else str(msg.content)
                    break
            if full_answer:
                yield full_answer

        # Save completed conversation to session
        session.add("human", message)
        session.add("ai", full_answer)


def _session_to_messages(session: Session) -> list[HumanMessage | AIMessage]:
    """Convert session history to LangChain message objects."""
    messages: list[HumanMessage | AIMessage] = []
    for role, content in session.get_history():
        if role == "human":
            messages.append(HumanMessage(content=content))
        elif role == "ai":
            messages.append(AIMessage(content=content))
    return messages
