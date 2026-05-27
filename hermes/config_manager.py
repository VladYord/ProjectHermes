"""Encrypted application config manager — stores user settings securely.

Provides:
- OS app-data directory resolution (Windows / macOS / Linux)
- AES-256-GCM encrypt/decrypt of a JSON settings blob (``config.enc``)
- A 32-byte random master key persisted as ``app_secret.key`` (owner-read-only)
- ``HermesAppConfig`` dataclass for all user-configurable fields
- ``merge_into_config`` to overlay encrypted settings onto the runtime HermesConfig
"""

from __future__ import annotations

import json
import os
import platform
import stat
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ---------------------------------------------------------------------------
# App-data directory
# ---------------------------------------------------------------------------

def get_app_data_dir() -> Path:
    """Return the OS-appropriate app-data directory, creating it if needed.

    - Windows  : ``%APPDATA%\\Hermes``
    - macOS    : ``~/Library/Application Support/Hermes``
    - Linux    : ``$XDG_CONFIG_HOME/hermes`` or ``~/.config/hermes``
    """
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    app_dir = base / "Hermes"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------

def _key_path() -> Path:
    return get_app_data_dir() / "app_secret.key"


def _config_enc_path() -> Path:
    return get_app_data_dir() / "config.enc"


def _load_or_create_key() -> bytes:
    """Return the 32-byte AES master key, generating and persisting it on first run."""
    path = _key_path()
    if path.exists():
        return path.read_bytes()

    key = os.urandom(32)
    path.write_bytes(key)

    # Restrict to owner read+write only (Unix).  Windows ACL is not set here;
    # the file lives under %APPDATA% which is already user-private.
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except (AttributeError, NotImplementedError, OSError):
        pass

    return key


# ---------------------------------------------------------------------------
# AES-256-GCM helpers
# ---------------------------------------------------------------------------

def _encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt with AES-256-GCM.  Returns ``nonce (12 B) || ciphertext+tag``."""
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, None)


def _decrypt(blob: bytes, key: bytes) -> bytes:
    """Decrypt AES-256-GCM blob produced by :func:`_encrypt`."""
    if len(blob) < 12:
        raise ValueError("Encrypted blob is too short")
    return AESGCM(key).decrypt(blob[:12], blob[12:], None)


# ---------------------------------------------------------------------------
# App config dataclass
# ---------------------------------------------------------------------------

@dataclass
class HermesAppConfig:
    """All user-configurable fields stored in the encrypted config file.

    Sensitive fields (API keys) are stored only in ``config.enc``, never in
    plain-text ``config.yaml`` or log output.
    """

    # Runtime preferences
    default_provider: str = "ollama"
    embedding_provider: str = "hash"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_base_url: str = ""
    azure_openai_deployment: str = "gpt-4o-mini"
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_embedding_model: str = "nomic-embed-text"


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_app_config() -> HermesAppConfig:
    """Decrypt and deserialise the app config.

    Returns :class:`HermesAppConfig` with defaults if no config file exists or
    if decryption fails (e.g. key mismatch after reinstall).
    """
    path = _config_enc_path()
    if not path.exists():
        return HermesAppConfig()
    try:
        key = _load_or_create_key()
        data = json.loads(_decrypt(path.read_bytes(), key))
        # Accept only known fields so future schema changes don't break loading
        known = {f for f in HermesAppConfig.__dataclass_fields__}
        return HermesAppConfig(**{k: v for k, v in data.items() if k in known})
    except Exception:
        return HermesAppConfig()


def save_app_config(config: HermesAppConfig) -> None:
    """Serialise, encrypt and persist the app config.

    Empty API keys are omitted from the saved blob (treated as "not set").
    """
    key = _load_or_create_key()
    data = asdict(config)
    # Remove empty sensitive fields so they don't shadow yaml defaults
    for field in ("openai_api_key", "gemini_api_key", "azure_openai_api_key"):
        if not data.get(field):
            data.pop(field, None)
    _config_enc_path().write_bytes(_encrypt(json.dumps(data).encode(), key))


# ---------------------------------------------------------------------------
# Runtime merge helper
# ---------------------------------------------------------------------------

def merge_into_config(hermes_cfg: "HermesConfig", app_cfg: HermesAppConfig) -> None:  # noqa: F821
    """Overlay encrypted settings onto an already-loaded :class:`HermesConfig`.

    Called at server startup so API keys stored in ``config.enc`` take priority
    over the plain-text ``config.yaml`` values.
    """
    providers = hermes_cfg.llm.providers

    if app_cfg.openai_api_key:
        providers.openai.api_key = app_cfg.openai_api_key
    if app_cfg.openai_model:
        providers.openai.model = app_cfg.openai_model

    if app_cfg.gemini_api_key:
        providers.gemini.api_key = app_cfg.gemini_api_key
    if app_cfg.gemini_model:
        providers.gemini.model = app_cfg.gemini_model

    if app_cfg.azure_openai_api_key:
        providers.azure_openai.api_key = app_cfg.azure_openai_api_key
    if app_cfg.azure_openai_base_url:
        providers.azure_openai.base_url = app_cfg.azure_openai_base_url
    if app_cfg.azure_openai_deployment:
        providers.azure_openai.deployment = app_cfg.azure_openai_deployment
    if app_cfg.azure_openai_api_version:
        providers.azure_openai.api_version = app_cfg.azure_openai_api_version
    if app_cfg.azure_openai_embedding_deployment:
        providers.azure_openai.embedding_deployment = app_cfg.azure_openai_embedding_deployment

    if app_cfg.ollama_base_url:
        providers.ollama.base_url = app_cfg.ollama_base_url
    if app_cfg.ollama_model:
        providers.ollama.model = app_cfg.ollama_model
    if app_cfg.ollama_embedding_model:
        providers.ollama.embedding_model = app_cfg.ollama_embedding_model

    if app_cfg.default_provider:
        hermes_cfg.llm.default_provider = app_cfg.default_provider
    if app_cfg.embedding_provider:
        hermes_cfg.vectordb.embedding_provider = app_cfg.embedding_provider
