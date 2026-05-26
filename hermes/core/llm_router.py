"""LLM Router — manages multiple LLM providers with config-based selection."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from hermes.config import get_config
from hermes.logging import get_logger

logger = get_logger("llm_router")


class LLMRouter:
    """Creates and caches LangChain ChatModel instances for each provider.

    Usage::

        router = LLMRouter()
        llm = router.get_provider("ollama")  # or "openai", "gemini"
        llm = router.get_default()
    """

    def __init__(self) -> None:
        self._cache: dict[str, BaseChatModel] = {}
        self._embedding_cache: dict[str, object] = {}

    # --- Provider factories ---

    @staticmethod
    def _build_ollama() -> BaseChatModel:
        from langchain_ollama import ChatOllama

        cfg = get_config().llm.providers.ollama
        logger.info("Initializing Ollama provider (model=%s, url=%s)", cfg.model, cfg.base_url)
        return ChatOllama(model=cfg.model, base_url=cfg.base_url)

    @staticmethod
    def _build_openai() -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        cfg = get_config().llm.providers.openai
        if not cfg.api_key:
            raise ValueError("OpenAI API key not configured (llm.providers.openai.api_key)")
        logger.info("Initializing OpenAI provider (model=%s)", cfg.model)
        return ChatOpenAI(model=cfg.model, api_key=cfg.api_key)

    @staticmethod
    def _build_gemini() -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        cfg = get_config().llm.providers.gemini
        if not cfg.api_key:
            raise ValueError("Gemini API key not configured (llm.providers.gemini.api_key)")
        logger.info("Initializing Gemini provider (model=%s)", cfg.model)
        return ChatGoogleGenerativeAI(model=cfg.model, google_api_key=cfg.api_key)

    @staticmethod
    def _build_azure_openai() -> BaseChatModel:
        from langchain_openai import AzureChatOpenAI

        cfg = get_config().llm.providers.azure_openai
        if not cfg.api_key:
            raise ValueError(
                "Azure OpenAI API key not configured "
                "(llm.providers.azure_openai.api_key or AZURE_OPENAI_API_KEY env var)"
            )
        logger.info(
            "Initializing Azure OpenAI provider (deployment=%s, url=%s)",
            cfg.deployment, cfg.base_url,
        )
        return AzureChatOpenAI(
            azure_endpoint=cfg.base_url,
            azure_deployment=cfg.deployment,
            api_version=cfg.api_version,
            api_key=cfg.api_key,
        )

    _BUILDERS: dict[str, str] = {
        "ollama": "_build_ollama",
        "openai": "_build_openai",
        "gemini": "_build_gemini",
        "azure_openai": "_build_azure_openai",
    }

    # --- Embedding provider factories ---

    @staticmethod
    def _build_embedding_hash() -> object:
        """Deterministic hash-based embedding — no network required."""
        import hashlib
        from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

        class _HashEmbeddingFn(EmbeddingFunction):
            def __init__(self, dim: int = 384) -> None:
                self._dim = dim

            def __call__(self, input: Documents) -> Embeddings:
                result: Embeddings = []
                for text in input:
                    h = hashlib.sha256(text.encode("utf-8")).digest()
                    repeated = (h * ((self._dim // len(h)) + 1))[:self._dim]
                    result.append([float(b) / 255.0 for b in repeated])
                return result

        logger.info("Using hash-based embedding function (dim=384, no network required)")
        return _HashEmbeddingFn()

    @staticmethod
    def _build_embedding_ollama() -> object:
        """Semantic embeddings via a locally running Ollama instance."""
        try:
            from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
        except ImportError:
            from chromadb.utils.embedding_functions.ollama_embedding_function import (
                OllamaEmbeddingFunction,
            )

        cfg = get_config().llm.providers.ollama
        logger.info(
            "Initializing Ollama embedding function (model=%s, url=%s)",
            cfg.embedding_model, cfg.base_url,
        )
        return OllamaEmbeddingFunction(
            url=f"{cfg.base_url}/api/embeddings",
            model_name=cfg.embedding_model,
        )

    @staticmethod
    def _build_embedding_azure_openai() -> object:
        """Semantic embeddings via Azure OpenAI (e.g. text-embedding-3-small)."""
        from openai import AzureOpenAI
        from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

        cfg = get_config().llm.providers.azure_openai
        if not cfg.api_key:
            raise ValueError(
                "Azure OpenAI API key not configured "
                "(llm.providers.azure_openai.api_key or AZURE_OPENAI_API_KEY env var)"
            )
        logger.info(
            "Initializing Azure OpenAI embedding function (deployment=%s)",
            cfg.embedding_deployment,
        )
        _api_key = cfg.api_key
        _deployment = cfg.embedding_deployment

        openai_client = AzureOpenAI(
            azure_endpoint=cfg.base_url,
            api_version=cfg.api_version,
            api_key=_api_key,
        )

        class _AzureEmbeddingFn(EmbeddingFunction):
            def __init__(self) -> None:
                self._client = openai_client
                self._deployment = _deployment

            def __call__(self, input: Documents) -> Embeddings:
                response = self._client.embeddings.create(
                    model=self._deployment,
                    input=list(input),
                )
                return [item.embedding for item in response.data]

        return _AzureEmbeddingFn()

    _EMBEDDING_BUILDERS: dict[str, str] = {
        "hash": "_build_embedding_hash",
        "ollama": "_build_embedding_ollama",
        "azure_openai": "_build_embedding_azure_openai",
    }

    # --- Public API ---

    def get_provider(self, name: str) -> BaseChatModel:
        """Get or create a ChatModel for the named provider."""
        name = name.lower()
        if name not in self._BUILDERS:
            raise ValueError(f"Unknown LLM provider: {name!r}. Available: {list(self._BUILDERS)}")

        if name not in self._cache:
            builder_name = self._BUILDERS[name]
            builder = getattr(self, builder_name)
            self._cache[name] = builder()

        return self._cache[name]

    def get_default(self) -> BaseChatModel:
        """Return the default provider from config."""
        default = get_config().llm.default_provider
        return self.get_provider(default)

    def list_providers(self) -> list[str]:
        """Return names of all available providers."""
        return list(self._BUILDERS.keys())

    def is_available(self, name: str) -> bool:
        """Check if a provider can be initialized (has required config)."""
        name = name.lower()
        if name not in self._BUILDERS:
            return False
        try:
            self.get_provider(name)
            return True
        except Exception:
            return False

    def get_embedding_fn(self, name: str | None = None) -> object:
        """Get or create an EmbeddingFunction for the named embedding provider.

        If name is None, uses vectordb.embedding_provider from config.
        Supported: "hash" (offline, default), "ollama", "azure_openai".

        Note: changing the embedding provider after documents have been ingested
        requires re-ingesting all documents, as vector dimensions will differ.
        """
        if name is None:
            name = get_config().vectordb.embedding_provider
        name = name.lower()
        if name not in self._EMBEDDING_BUILDERS:
            raise ValueError(
                f"Unknown embedding provider: {name!r}. "
                f"Available: {list(self._EMBEDDING_BUILDERS)}"
            )
        if name not in self._embedding_cache:
            builder_name = self._EMBEDDING_BUILDERS[name]
            builder = getattr(self, builder_name)
            self._embedding_cache[name] = builder()
        return self._embedding_cache[name]
