"""Tests for LLM Router."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hermes.config import reset_config


@pytest.fixture(autouse=True)
def _clean_config():
    reset_config()
    yield
    reset_config()


@pytest.fixture()
def router():
    from hermes.core.llm_router import LLMRouter
    return LLMRouter()


class TestLLMRouter:
    def test_list_providers(self, router):
        providers = router.list_providers()
        assert "ollama" in providers
        assert "openai" in providers
        assert "gemini" in providers

    def test_unknown_provider_raises(self, router):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            router.get_provider("unknown")

    def test_get_default_provider(self, router):
        """Default is ollama — this just tests the path, not the actual connection."""
        with patch("hermes.core.llm_router.LLMRouter._build_ollama") as mock:
            mock.return_value = MagicMock()
            llm = router.get_default()
            assert llm is not None
            mock.assert_called_once()

    def test_caches_provider_instance(self, router):
        with patch("hermes.core.llm_router.LLMRouter._build_ollama") as mock:
            mock.return_value = MagicMock()
            llm1 = router.get_provider("ollama")
            llm2 = router.get_provider("ollama")
            assert llm1 is llm2
            mock.assert_called_once()  # Only built once

    def test_openai_without_key_raises(self, router, monkeypatch):
        """OpenAI should fail if api_key is not set."""
        import hermes.config as config_module
        from hermes.config import load_config

        cfg = load_config()
        cfg.llm.providers.openai.api_key = ""
        config_module._config = cfg

        with pytest.raises(ValueError, match="OpenAI API key"):
            router.get_provider("openai")

    def test_gemini_without_key_raises(self, router, monkeypatch):
        """Gemini should fail if api_key is not set."""
        import hermes.config as config_module
        from hermes.config import load_config

        cfg = load_config()
        cfg.llm.providers.gemini.api_key = ""
        config_module._config = cfg

        with pytest.raises(ValueError, match="Gemini API key"):
            router.get_provider("gemini")


class TestEmbeddingRouter:
    def test_default_embedding_fn_returns_hash(self, router):
        """Default embedding provider (hash) should work with no network."""
        ef = router.get_embedding_fn()
        assert ef is not None

    def test_hash_embedding_produces_correct_output(self, router):
        ef = router.get_embedding_fn("hash")
        result = ef(["hello world", "another document"])
        assert len(result) == 2
        assert len(result[0]) == 384
        assert all(0.0 <= v <= 1.0 for v in result[0])

    def test_hash_embedding_is_deterministic(self, router):
        ef = router.get_embedding_fn("hash")
        r1 = ef(["same text"])
        r2 = ef(["same text"])
        # Results may be numpy arrays; compare element-wise
        assert list(r1[0]) == list(r2[0])

    def test_unknown_embedding_provider_raises(self, router):
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            router.get_embedding_fn("not_a_provider")

    def test_caches_embedding_fn_instance(self, router):
        ef1 = router.get_embedding_fn("hash")
        ef2 = router.get_embedding_fn("hash")
        assert ef1 is ef2

    def test_azure_embedding_without_key_raises(self, router):
        import hermes.config as config_module
        from hermes.config import load_config

        cfg = load_config()
        cfg.llm.providers.azure_openai.api_key = ""
        config_module._config = cfg

        with pytest.raises(ValueError, match="Azure OpenAI API key"):
            router.get_embedding_fn("azure_openai")
