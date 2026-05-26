"""Abstract base class for document parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    """Base class for all document parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> list[str]:
        """Parse a file and return a list of text segments.

        Each segment is a logical unit (e.g., a page, a section).
        Chunking is handled separately.
        """

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Return True if this parser can handle the given file."""
