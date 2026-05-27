"""Configuration loader and Pydantic models for Hermes."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


# --- Pydantic Config Models ---


class AuthConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    auth: AuthConfig = Field(default_factory=AuthConfig)


class OllamaProviderConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3.1"
    embedding_model: str = "nomic-embed-text"


class OpenAIProviderConfig(BaseModel):
    api_key: str = ""
    model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"


class GeminiProviderConfig(BaseModel):
    api_key: str = ""
    model: str = "gemini-pro"


class AzureOpenAIConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    deployment: str = "gpt-4o-mini"
    api_version: str = "2024-08-01-preview"
    embedding_deployment: str = "text-embedding-3-small"


class ProvidersConfig(BaseModel):
    ollama: OllamaProviderConfig = Field(default_factory=OllamaProviderConfig)
    openai: OpenAIProviderConfig = Field(default_factory=OpenAIProviderConfig)
    gemini: GeminiProviderConfig = Field(default_factory=GeminiProviderConfig)
    azure_openai: AzureOpenAIConfig = Field(default_factory=AzureOpenAIConfig)


class LLMConfig(BaseModel):
    default_provider: str = "ollama"
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)


class VectorDBConfig(BaseModel):
    provider: str = "chromadb"
    persist_directory: str = "./data/chromadb"
    # Which provider generates embeddings: "hash" (offline), "ollama", "azure_openai"
    embedding_provider: str = "hash"


class IngestionConfig(BaseModel):
    chunk_size: int = 1000
    chunk_overlap: int = 200
    supported_extensions: list[str] = Field(default_factory=lambda: [
        ".pdf", ".txt", ".md", ".docx",
        ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs",
        ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
    ])


class OCRConfig(BaseModel):
    engine: str = "tesseract"
    language: str = "eng"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class HermesConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vectordb: VectorDBConfig = Field(default_factory=VectorDBConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    ocr: OCRConfig = Field(default_factory=OCRConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# --- Environment Variable Expansion ---

_ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _expand_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} with the environment variable value, or empty string."""
    def replacer(match: re.Match) -> str:
        return os.environ.get(match.group(1), "")
    return _ENV_VAR_PATTERN.sub(replacer, value)


def _expand_env_recursive(data: object) -> object:
    """Walk a nested dict/list and expand env vars in all string values."""
    if isinstance(data, str):
        return _expand_env_vars(data)
    if isinstance(data, dict):
        return {k: _expand_env_recursive(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_env_recursive(item) for item in data]
    return data


# --- Config Loading ---

_CONFIG_SEARCH_PATHS = [
    Path("config.yaml"),
    Path("config.yml"),
    Path.home() / ".hermes" / "config.yaml",
]


def find_config_file(explicit_path: Optional[str | Path] = None) -> Optional[Path]:
    """Find the config file. Explicit path takes priority, then search defaults."""
    if explicit_path:
        p = Path(explicit_path)
        if p.is_file():
            return p
        return None
    for candidate in _CONFIG_SEARCH_PATHS:
        if candidate.is_file():
            return candidate
    return None


def load_config(config_path: Optional[str | Path] = None) -> HermesConfig:
    """Load configuration from YAML file with env var expansion.

    Falls back to defaults if no config file is found.
    When ``HERMES_PACKAGED=1`` is set the vector store and session paths are
    redirected to the OS app-data directory so data survives app updates.
    """
    path = find_config_file(config_path)
    if path is None:
        config = HermesConfig()
    else:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        expanded = _expand_env_recursive(raw)
        config = HermesConfig.model_validate(expanded)

    # Override data paths when running as a packaged desktop app.
    if os.environ.get("HERMES_PACKAGED") == "1":
        from hermes.config_manager import get_app_data_dir
        app_data = get_app_data_dir()
        config.vectordb.persist_directory = str(app_data / "chromadb")

    return config


# --- Singleton-ish access ---

_config: Optional[HermesConfig] = None


def get_config() -> HermesConfig:
    """Get the global config instance. Loads from default location on first call."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global config (mainly for testing)."""
    global _config
    _config = None
