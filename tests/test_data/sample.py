"""Sample Python file for testing code parsing."""

from dataclasses import dataclass


@dataclass
class Document:
    """Represents an ingested document."""

    name: str
    content: str
    doc_type: str

    def summary(self) -> str:
        """Return a short summary of the document."""
        return f"{self.name} ({self.doc_type}): {len(self.content)} chars"


def process_documents(docs: list[Document]) -> list[str]:
    """Process a list of documents and return summaries."""
    results = []
    for doc in docs:
        results.append(doc.summary())
    return results


class DocumentStore:
    """In-memory document store for testing."""

    def __init__(self):
        self._docs: dict[str, Document] = {}

    def add(self, doc_id: str, doc: Document) -> None:
        self._docs[doc_id] = doc

    def get(self, doc_id: str) -> Document | None:
        return self._docs.get(doc_id)

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._docs:
            del self._docs[doc_id]
            return True
        return False

    def list_all(self) -> list[str]:
        return list(self._docs.keys())
