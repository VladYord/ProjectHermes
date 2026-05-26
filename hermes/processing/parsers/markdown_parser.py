"""Markdown file parser."""

from __future__ import annotations

from pathlib import Path

from hermes.processing.parsers.base import BaseParser


class MarkdownParser(BaseParser):
    """Parser for .md files. Splits on top-level headings for better chunking."""

    EXTENSIONS = {".md", ".markdown"}

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.EXTENSIONS

    def parse(self, file_path: Path) -> list[str]:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []

        # Split by top-level and second-level headings to preserve section structure
        sections: list[str] = []
        current: list[str] = []

        for line in text.splitlines(keepends=True):
            if line.startswith(("# ", "## ")) and current:
                section_text = "".join(current).strip()
                if section_text:
                    sections.append(section_text)
                current = [line]
            else:
                current.append(line)

        # Don't forget the last section
        if current:
            section_text = "".join(current).strip()
            if section_text:
                sections.append(section_text)

        return sections if sections else [text]
