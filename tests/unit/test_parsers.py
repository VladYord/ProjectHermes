"""Tests for document parsers."""

from pathlib import Path

import pytest

from hermes.processing.parsers.text_parser import TextParser
from hermes.processing.parsers.markdown_parser import MarkdownParser
from hermes.processing.parsers.code_parser import CodeParser


class TestTextParser:
    def test_supports_txt(self, sample_txt: Path):
        parser = TextParser()
        assert parser.supports(sample_txt)

    def test_does_not_support_md(self, sample_md: Path):
        parser = TextParser()
        assert not parser.supports(sample_md)

    def test_parse_returns_text(self, sample_txt: Path):
        parser = TextParser()
        segments = parser.parse(sample_txt)
        assert len(segments) == 1
        assert "Python programming" in segments[0]
        assert "vector databases" in segments[0]

    def test_parse_empty_file(self, tmp_path: Path):
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        parser = TextParser()
        assert parser.parse(empty) == []


class TestMarkdownParser:
    def test_supports_md(self, sample_md: Path):
        parser = MarkdownParser()
        assert parser.supports(sample_md)

    def test_parse_splits_on_headings(self, sample_md: Path):
        parser = MarkdownParser()
        sections = parser.parse(sample_md)
        # Should split on # and ## headings
        assert len(sections) >= 3
        # First section should have the title
        assert "Sample Markdown Document" in sections[0]

    def test_parse_preserves_content(self, sample_md: Path):
        parser = MarkdownParser()
        sections = parser.parse(sample_md)
        all_text = "\n".join(sections)
        assert "Transport Layer" in all_text
        assert "Parsers" in all_text


class TestCodeParser:
    def test_supports_py(self, sample_py: Path):
        parser = CodeParser()
        assert parser.supports(sample_py)

    def test_parse_wraps_in_fence(self, sample_py: Path):
        parser = CodeParser()
        segments = parser.parse(sample_py)
        assert len(segments) == 1
        assert segments[0].startswith("```python")
        assert "class Document" in segments[0]

    def test_get_language(self, tmp_path: Path):
        assert CodeParser.get_language(tmp_path / "test.py") == "python"
        assert CodeParser.get_language(tmp_path / "test.js") == "javascript"
        assert CodeParser.get_language(tmp_path / "test.rs") == "rust"
