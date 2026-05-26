"""Tests for the chunking engine."""

from hermes.processing.chunking import chunk_text


def test_chunk_short_text():
    """Short text that fits in one chunk should produce one chunk."""
    segments = ["Hello world, this is a short test."]
    chunks = chunk_text(segments, source_name="test.txt", doc_type="text")
    assert len(chunks) == 1
    assert chunks[0].text == segments[0]
    assert chunks[0].metadata["source"] == "test.txt"


def test_chunk_long_text():
    """Long text should be split into multiple chunks."""
    # Create text longer than default chunk size
    long_text = "This is a sentence about testing. " * 100
    segments = [long_text]
    chunks = chunk_text(
        segments,
        source_name="long.txt",
        doc_type="text",
        chunk_size=200,
        chunk_overlap=50,
    )
    assert len(chunks) > 1
    # Each chunk should be within size limits (approximately)
    for chunk in chunks:
        assert len(chunk.text) <= 250  # some tolerance for split boundaries


def test_chunk_preserves_metadata():
    """Each chunk should carry source metadata."""
    segments = ["First segment.", "Second segment."]
    chunks = chunk_text(segments, source_name="doc.md", doc_type="markdown")
    for chunk in chunks:
        assert chunk.metadata["source"] == "doc.md"
        assert chunk.metadata["doc_type"] == "markdown"
        assert "segment_index" in chunk.metadata
        assert "chunk_index" in chunk.metadata


def test_chunk_multiple_segments():
    """Multiple segments should each be chunked independently."""
    segments = ["Segment one content.", "Segment two content."]
    chunks = chunk_text(segments, source_name="test.txt", doc_type="text")
    assert len(chunks) == 2
    assert chunks[0].metadata["segment_index"] == 0
    assert chunks[1].metadata["segment_index"] == 1
