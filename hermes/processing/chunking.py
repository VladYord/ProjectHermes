"""Text chunking strategies for the document processing pipeline."""

from __future__ import annotations

from hermes.config import get_config
from hermes.models.domain import Chunk


def chunk_text(
    segments: list[str],
    *,
    source_name: str = "",
    doc_type: str = "",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split text segments into overlapping chunks with metadata.

    Uses RecursiveCharacterTextSplitter from LangChain for robust splitting.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    cfg = get_config().ingestion
    size = chunk_size or cfg.chunk_size
    overlap = chunk_overlap or cfg.chunk_overlap

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    for seg_idx, segment in enumerate(segments):
        split_texts = splitter.split_text(segment)
        for chunk_idx, text in enumerate(split_texts):
            chunks.append(Chunk(
                text=text,
                metadata={
                    "source": source_name,
                    "doc_type": doc_type,
                    "segment_index": seg_idx,
                    "chunk_index": chunk_idx,
                },
            ))

    return chunks
