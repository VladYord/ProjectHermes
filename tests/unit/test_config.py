"""Tests for the configuration system."""

from pathlib import Path

from hermes.config import HermesConfig, load_config, _expand_env_vars


def test_default_config():
    """Default config should have sensible values."""
    cfg = HermesConfig()
    assert cfg.server.host == "0.0.0.0"
    assert cfg.server.port == 8000
    assert cfg.llm.default_provider == "ollama"
    assert cfg.vectordb.provider == "chromadb"


def test_load_config_from_file(tmp_path: Path):
    """Config loaded from YAML should override defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "server:\n  port: 9999\nllm:\n  default_provider: openai\n"
    )
    cfg = load_config(config_file)
    assert cfg.server.port == 9999
    assert cfg.llm.default_provider == "openai"
    # Non-overridden values keep defaults
    assert cfg.server.host == "0.0.0.0"


def test_load_config_missing_file():
    """Missing file should fall back to defaults."""
    cfg = load_config("/nonexistent/path/config.yaml")
    assert cfg.server.port == 8000


def test_env_var_expansion(monkeypatch):
    """Environment variables should be expanded in values."""
    monkeypatch.setenv("TEST_KEY_123", "secret-value")
    result = _expand_env_vars("${TEST_KEY_123}")
    assert result == "secret-value"


def test_env_var_expansion_missing():
    """Missing env vars should expand to empty string."""
    result = _expand_env_vars("${DEFINITELY_NOT_SET_XYZ}")
    assert result == ""
