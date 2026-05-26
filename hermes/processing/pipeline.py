"""Document processing pipeline — orchestrates parsing and chunking."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from hermes.config import get_config
from hermes.logging import get_logger
from hermes.models.domain import Chunk, DocumentType, IngestResult
from hermes.processing.chunking import chunk_text
from hermes.processing.parsers.base import BaseParser
from hermes.processing.parsers.code_parser import CodeParser
from hermes.processing.parsers.docx_parser import DocxParser
from hermes.processing.parsers.markdown_parser import MarkdownParser
from hermes.processing.parsers.ocr_parser import OCRParser
from hermes.processing.parsers.pdf_parser import PDFParser
from hermes.processing.parsers.text_parser import TextParser

logger = get_logger("pipeline")

# Extension → DocumentType mapping
_EXTENSION_TYPE_MAP: dict[str, DocumentType] = {
    ".txt": DocumentType.TEXT,
    ".md": DocumentType.MARKDOWN,
    ".markdown": DocumentType.MARKDOWN,
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".png": DocumentType.IMAGE,
    ".jpg": DocumentType.IMAGE,
    ".jpeg": DocumentType.IMAGE,
    ".tiff": DocumentType.IMAGE,
    ".bmp": DocumentType.IMAGE,
}
# Code extensions
for ext in CodeParser.EXTENSIONS:
    _EXTENSION_TYPE_MAP[ext] = DocumentType.CODE


class DocumentProcessor:
    """Orchestrates the full document processing pipeline.

    detect type → parse → chunk → return chunks (storage handled by service layer)
    """

    def __init__(self) -> None:
        self._parsers: list[BaseParser] = [
            TextParser(),
            MarkdownParser(),
            PDFParser(),
            DocxParser(),
            CodeParser(),
            OCRParser(),
        ]

    def detect_type(self, file_path: Path) -> DocumentType:
        """Determine document type from file extension."""
        ext = file_path.suffix.lower()
        if ext in _EXTENSION_TYPE_MAP:
            return _EXTENSION_TYPE_MAP[ext]
        raise ValueError(f"Unsupported file type: {ext}")

    def _get_parser(self, file_path: Path) -> BaseParser:
        """Find the appropriate parser for a file."""
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser
        raise ValueError(f"No parser found for: {file_path}")

    def is_supported(self, file_path: Path) -> bool:
        """Check if a file type is supported."""
        ext = file_path.suffix.lower()
        return ext in get_config().ingestion.supported_extensions

    def process(self, file_path: Path) -> tuple[list[Chunk], DocumentType]:
        """Process a file through the full pipeline: parse → chunk.

        Returns the chunks and the detected document type.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        if not self.is_supported(path):
            raise ValueError(f"Unsupported file type: {path.suffix}")

        doc_type = self.detect_type(path)
        logger.info("Processing %s (type: %s)", path.name, doc_type.value)

        parser = self._get_parser(path)
        segments = parser.parse(path)

        if not segments:
            logger.warning("No text extracted from %s", path.name)
            return [], doc_type

        chunks = chunk_text(
            segments,
            source_name=path.name,
            doc_type=doc_type.value,
        )
        logger.info("Created %d chunks from %s", len(chunks), path.name)

        return chunks, doc_type
