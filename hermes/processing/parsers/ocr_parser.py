"""OCR parser for scanned images and image-based PDFs.

REQUIRES: Tesseract OCR installed on the system.
Install:
  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
  - Linux: sudo apt install tesseract-ocr
  - macOS: brew install tesseract
"""

from __future__ import annotations

from pathlib import Path

from hermes.processing.parsers.base import BaseParser


class OCRParser(BaseParser):
    """Parser for image files using Tesseract OCR."""

    EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

    def supports(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.EXTENSIONS

    def parse(self, file_path: Path) -> list[str]:
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise RuntimeError(
                "OCR requires pytesseract and Pillow. "
                "Install them with: pip install pytesseract Pillow"
            ) from e

        from hermes.config import get_config

        cfg = get_config().ocr
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang=cfg.language)
        return [text] if text.strip() else []
