"""
Hermes Phase 1 — Interactive End-to-End Test Script
=====================================================
Tests the REST API server in sequence:
  1. Health check
  2. List providers
  3. Chat WITHOUT ingested knowledge   (baseline)
  4. Ingest a PDF file
  5. Chat WITH ingested knowledge      (RAG answer)
  6. List documents
  7. (Optional) Delete the ingested document

Usage:
    # Start the server first:
    #   python -m hermes.server
    #   (or: uvicorn hermes.server:app --reload)

    python tools/test_server.py --pdf path/to/your/file.pdf --question "Your question here"

    # Additional flags:
    #   --url      Base URL of the server (default: http://localhost:8000)
    #   --provider LLM provider to use   (default: from server config)
    #   --no-delete Keep the ingested document after the test
    #   --stream    Use SSE streaming for chat responses
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import httpx

# ── Config ────────────────────────────────────────────────────────

DEFAULT_URL = "http://localhost:8000"
DEFAULT_QUESTION = (
    "What are the main topics covered in the document? "
    "Summarise the key points."
)

# ── Helpers ───────────────────────────────────────────────────────

def _sep(title: str = "") -> None:
    width = 72
    if title:
        print(f"\n{'─' * 3} {title} {'─' * (width - len(title) - 5)}")
    else:
        print("─" * width)


def _ok(label: str, value: object = "") -> None:
    print(f"  ✓  {label}: {value}" if value != "" else f"  ✓  {label}")


def _fail(label: str, detail: str = "") -> None:
    print(f"  ✗  {label}: {detail}" if detail else f"  ✗  {label}")
    sys.exit(1)


def _chat(client: httpx.Client, base: str, message: str, session_id: str,
          provider: str | None, stream: bool) -> str:
    """Send a chat request and return the answer text."""
    payload: dict = {"message": message, "session_id": session_id, "stream": stream}
    if provider:
        payload["provider"] = provider

    if stream:
        answer_parts: list[str] = []
        print("  [streaming] ", end="", flush=True)
        with client.stream("POST", f"{base}/api/chat", json=payload, timeout=120) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                event = json.loads(raw)
                if "token" in event:
                    print(event["token"], end="", flush=True)
                    answer_parts.append(event["token"])
                elif event.get("done"):
                    print()  # newline after stream
                elif "error" in event:
                    _fail("Stream error", event["error"])
        return "".join(answer_parts)
    else:
        r = client.post(f"{base}/api/chat", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        return data["answer"], data.get("sources", [])


# ── Main test flow ────────────────────────────────────────────────

def run(base_url: str, pdf_path: str, question: str,
        provider: str | None, stream: bool, keep: bool) -> None:

    client = httpx.Client(timeout=30)
    session_id = f"test-{int(time.time())}"

    # ── 1. Health check ───────────────────────────────────────────
    _sep("1. Health Check")
    r = client.get(f"{base_url}/api/health")
    if r.status_code != 200:
        _fail("Server not reachable", f"HTTP {r.status_code}. Is it running at {base_url}?")
    data = r.json()
    _ok("Server is up", f"Hermes v{data['version']}")

    # ── 2. Providers ──────────────────────────────────────────────
    _sep("2. LLM Providers")
    r = client.get(f"{base_url}/api/providers")
    r.raise_for_status()
    pdata = r.json()
    _ok("Default provider", pdata["default"])
    for p in pdata["providers"]:
        status = "available" if p["available"] else "not configured"
        print(f"       {'✓' if p['available'] else '○'}  {p['name']} ({status})")

    active_provider = provider or pdata["default"]

    # ── 3. Chat WITHOUT knowledge ─────────────────────────────────
    _sep("3. Chat WITHOUT ingested knowledge (baseline)")
    print(f"  Question : {question}")
    print(f"  Provider : {active_provider}")
    print()

    if stream:
        answer_before = _chat(client, base_url, question, session_id, provider, stream=True)
        sources_before = []
    else:
        answer_before, sources_before = _chat(client, base_url, question, session_id, provider, stream=False)
        print(f"  Answer   : {answer_before}")

    if sources_before:
        print(f"  Sources  : {len(sources_before)} chunks referenced")
    else:
        print("  Sources  : none (no documents ingested yet — expected)")

    # ── 4. Ingest PDF ─────────────────────────────────────────────
    _sep("4. Ingest PDF document")
    print(f"  File: {pdf_path}")
    print()

    with open(pdf_path, "rb") as f:
        r = client.post(
            f"{base_url}/api/ingest/upload",
            files={"file": (pdf_path.split("\\")[-1].split("/")[-1], f, "application/pdf")},
            timeout=900,  # large books need time: parsing + N*batch embedding calls
        )

    if r.status_code != 200:
        _fail("Ingestion failed", f"HTTP {r.status_code}: {r.text}")

    ing = r.json()
    doc_id = ing["document_id"]
    _ok("Document ingested", ing["document_name"])
    _ok("Chunks created", ing["chunks_created"])
    _ok("Processing time", f"{ing['processing_time_seconds']:.2f}s")
    _ok("Document ID", doc_id)

    # ── 5. Chat WITH knowledge ────────────────────────────────────
    _sep("5. Chat WITH ingested knowledge (RAG)")
    print(f"  Question : {question}")
    print(f"  Provider : {active_provider}")
    print()

    # Use a fresh session so there's no chat history bias
    rag_session = f"{session_id}-rag"
    if stream:
        answer_after = _chat(client, base_url, question, rag_session, provider, stream=True)
        sources_after = []
    else:
        answer_after, sources_after = _chat(client, base_url, question, rag_session, provider, stream=False)
        print(f"  Answer   : {answer_after}")

    if sources_after:
        print(f"\n  Sources referenced ({len(sources_after)}):")
        for s in sources_after:
            print(f"    • [{s['document']}]  score={s['score']:.3f}")
            print(f"      \"{s['chunk'][:120]}...\"")

    # ── 6. Document list ──────────────────────────────────────────
    _sep("6. Document list")
    r = client.get(f"{base_url}/api/documents")
    r.raise_for_status()
    docs = r.json()["documents"]
    _ok("Total documents in knowledge base", len(docs))
    for d in docs:
        print(f"       • {d['name']}  ({d['chunks_count']} chunks, type={d['doc_type']})")

    # ── 7. Cleanup ────────────────────────────────────────────────
    if not keep:
        _sep("7. Cleanup")
        r = client.delete(f"{base_url}/api/documents/{doc_id}")
        if r.status_code == 200:
            _ok("Document deleted", doc_id)
        else:
            print(f"  ⚠  Could not delete document: HTTP {r.status_code}")
    else:
        _sep("7. Cleanup")
        print("  Skipped (--no-delete). Document remains in the knowledge base.")

    # ── Summary ───────────────────────────────────────────────────
    _sep("Summary")
    print(f"\n  BEFORE RAG:  {answer_before[:200]}")
    print(f"\n  AFTER  RAG:  {answer_after[:200]}")
    _sep()


# ── Entry point ───────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Hermes Phase 1 end-to-end test")
    p.add_argument("--pdf",      required=True,  help="Path to the PDF file to ingest")
    p.add_argument("--question", default=DEFAULT_QUESTION,
                   help="Question to ask before and after ingestion")
    p.add_argument("--url",      default=DEFAULT_URL, help="Hermes server base URL")
    p.add_argument("--provider", default=None,
                   help="LLM provider override (e.g. azure_openai, ollama, openai)")
    p.add_argument("--stream",   action="store_true", help="Use SSE streaming for chat")
    p.add_argument("--no-delete", dest="keep", action="store_true",
                   help="Keep the ingested document after the test")
    args = p.parse_args()

    run(
        base_url=args.url.rstrip("/"),
        pdf_path=args.pdf,
        question=args.question,
        provider=args.provider,
        stream=args.stream,
        keep=args.keep,
    )


if __name__ == "__main__":
    main()
