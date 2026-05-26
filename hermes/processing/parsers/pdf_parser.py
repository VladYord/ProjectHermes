"""PDF parser using PyMuPDF (fitz)."""

from __future__ import annotations

from pathlib import Path

from hermes.processing.parsers.base import BaseParser


class PDFParser(BaseParser):
    """Parser for PDF files. Returns one text segment per page."""

    EXTENSIONS = {".pdf"}

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.EXTENSIONS

    def parse(self, file_path: Path) -> list[str]:
        import fitz  # PyMuPDF

        pages: list[str] = []
        with fitz.open(str(file_path)) as doc:
            for page_num, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    pages.append(text)
        return pages
