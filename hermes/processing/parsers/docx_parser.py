"""DOCX parser using python-docx."""

from __future__ import annotations

from pathlib import Path

from hermes.processing.parsers.base import BaseParser


class DocxParser(BaseParser):
    """Parser for .docx (Microsoft Word) files."""

    EXTENSIONS = {".docx"}

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.EXTENSIONS

    def parse(self, file_path: Path) -> list[str]:
        from docx import Document

        doc = Document(str(file_path))
        paragraphs: list[str] = []
        current_section: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            # Split on heading styles to preserve document structure
            if para.style and para.style.name.startswith("Heading"):
                if current_section:
                    paragraphs.append("\n".join(current_section))
                    current_section = []
            current_section.append(text)

        if current_section:
            paragraphs.append("\n".join(current_section))

        return paragraphs
