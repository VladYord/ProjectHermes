"""Shared pytest fixtures for Hermes tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hermes.config import HermesConfig, load_config, reset_config


TEST_DATA_DIR = Path(__file__).parent / "test_data"


@pytest.fixture(autouse=True)
def _reset_global_config():
    """Reset the global config singleton between tests."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def default_config() -> HermesConfig:
    """Return a default HermesConfig (no file, pure defaults)."""
    return HermesConfig()


@pytest.fixture
def test_data_dir() -> Path:
    """Path to the test data directory."""
    return TEST_DATA_DIR


@pytest.fixture
def sample_txt(test_data_dir: Path) -> Path:
    return test_data_dir / "sample.txt"


@pytest.fixture
def sample_md(test_data_dir: Path) -> Path:
    return test_data_dir / "sample.md"


@pytest.fixture
def sample_py(test_data_dir: Path) -> Path:
    return test_data_dir / "sample.py"


@pytest.fixture
def tmp_chromadb(tmp_path: Path) -> Path:
    """Temporary directory for ChromaDB during tests."""
    db_dir = tmp_path / "chromadb"
    db_dir.mkdir()
    return db_dir
