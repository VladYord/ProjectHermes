"""Plain text file parser."""

from __future__ import annotations

from pathlib import Path

from hermes.processing.parsers.base import BaseParser


class TextParser(BaseParser):
    """Parser for plain .txt files."""

    EXTENSIONS = {".txt"}

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.EXTENSIONS

    def parse(self, file_path: Path) -> list[str]:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return [text] if text.strip() else []
