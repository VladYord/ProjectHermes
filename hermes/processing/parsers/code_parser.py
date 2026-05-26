"""Code file parser with language-aware handling."""

from __future__ import annotations

from pathlib import Path

from hermes.processing.parsers.base import BaseParser

# Map extensions to language names for metadata
_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c_header",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
}


class CodeParser(BaseParser):
    """Parser for source code files. Returns the full file as a single segment."""

    EXTENSIONS = set(_LANGUAGE_MAP.keys())

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.EXTENSIONS

    def parse(self, file_path: Path) -> list[str]:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []

        language = _LANGUAGE_MAP.get(file_path.suffix.lower(), "unknown")
        # Wrap in a code fence to preserve language context through the pipeline
        return [f"```{language}\n# File: {file_path.name}\n{text}\n```"]

    @staticmethod
    def get_language(file_path: Path) -> str:
        return _LANGUAGE_MAP.get(file_path.suffix.lower(), "unknown")
