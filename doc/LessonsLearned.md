# Lessons Learned — Project Hermes

---

## LL-01 — Embedding Model Dimension Mismatch

**Date:** 2026-04-08
**Error:** `chromadb.errors.InvalidArgumentError: Collection expecting embedding with dimension of 384, got 1536`

### What happened
The ChromaDB collection was initially created using `_HashEmbeddingFunction` (384 dimensions) as the offline fallback. When the default embedding provider was switched to Bosch LLM Farm (`text-embedding-3-small`, 1536 dimensions), the existing collection rejected all new queries and ingestion attempts because the vector dimensions did not match.

### Root cause
ChromaDB locks the vector dimension of a collection at creation time. It cannot be changed afterwards without dropping and recreating the collection — and all stored data with it.

### Fix applied
Delete the entire `data\chromadb\` directory while the server is stopped, then restart. The server recreates a fresh collection with the correct dimensions on startup. All documents must be re-ingested.

```powershell
# Stop server first, then:
Remove-Item -Recurse -Force "c:\Project Hermes\data\chromadb"
```

### Rules to carry forward
- **Document the active embedding model** for every deployment. Treat it as a schema version.
- **Never delete just the segment folder** (e.g. `data\chromadb\64fa7f3c-.../`). The `chroma.sqlite3` file holds the dimension metadata — delete the whole `data\chromadb\` directory.
- **Switching embedding models = mandatory full re-ingest.** Budget time for this when planning changes (a 3758-chunk textbook takes ~2–3 minutes on the Bosch farm).
- **Never mix embedding models** within one collection. Vectors from different models live in incompatible geometric spaces — similarity search results will be meaningless.

### Embedding model dimension reference

| Model | Dimensions | Notes |
|---|---|---|
| `_HashEmbeddingFunction` (Hermes fallback) | 384 | No network, not semantic |
| `nomic-embed-text` via Ollama | 768 | Local, good quality |
| `text-embedding-3-small` (Bosch LLM Farm) | 1536 | Default for production |
| `text-embedding-3-large` (OpenAI) | 3072 | Highest quality, higher cost |

---

## LL-02 — Embedding API Batch Size Limit

**Date:** 2026-04-08
**Error:** `httpx.HTTPStatusError: Client error '400 model_error'` during ingestion

### What happened
When ingesting a large PDF (Advanced Engineering Mathematics, 3758 chunks), all chunks were passed to the Bosch LLM Farm embedding API in a single call. The API rejected this with `400 model_error`.

### Root cause
Embedding APIs have a per-request item limit. The Bosch farm variant of `text-embedding-3-small` rejected calls with more than ~100 items. The original `KnowledgeService.ingest_file()` code called `collection.add()` with all chunks at once.

### Fix applied
Batched `collection.add()` calls in [hermes/services/knowledge_service.py](../hermes/services/knowledge_service.py) with a configurable `batch_size = 96`:

```python
batch_size = 96
for start_idx in range(0, len(ids), batch_size):
    end_idx = start_idx + batch_size
    self._collection.add(
        ids=ids[start_idx:end_idx],
        documents=documents[start_idx:end_idx],
        metadatas=metadatas[start_idx:end_idx],
    )
```

### Rules to carry forward
- **Always batch embedding API calls.** Never send more than 96–128 items per call to the Bosch farm. Test any new provider with a small batch first.
- **3758 chunks ÷ 96 per batch = ~40 API round-trips.** For large books, ingestion will take 2–4 minutes. This is expected.
- If you change provider, re-tune `batch_size` — different providers have different limits.

---

## LL-03 — Chunk Size vs. Embedding Model Token Limit

**Date:** 2026-04-08

### Rule
Every chunk must fit within the embedding model's token limit. The rough conversion is:

```
chunk_size (chars) ÷ 4 ≈ tokens
```

| Model | Token limit | Max safe chunk size (chars) |
|---|---|---|
| `text-embedding-3-small` | 8191 tokens | ~32 000 chars |
| `nomic-embed-text` | 8192 tokens | ~32 000 chars |

Our current chunk size of **1000 chars ≈ 250 tokens** is well within all limits.

### Recommendation for technical/textbook content
1000-char chunks are on the small side for dense content like engineering mathematics. Short chunks may split equations or derivations across boundaries, reducing retrieval quality. Consider increasing to **1500–2000 chars** for textbook ingestion.

Tuning levers in [config.yaml](../config.yaml):
```yaml
ingestion:
  chunk_size: 1000      # increase to 1500–2000 for textbooks
  chunk_overlap: 200    # increase overlap for dense content
```

Higher `chunk_overlap` helps when a concept spans a chunk boundary — it ensures the concept appears fully in at least one chunk.

---

## LL-04 — Corporate Proxy + SSL Certificate Verification

**Date:** 2026-04-08
**Error:** `httpx.ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate`

### What happened
The corporate proxy (`http://localhost:3128`) intercepts HTTPS traffic and re-signs it with an internal CA certificate that is not in Python's default certificate store. This caused SSL verification failures for all outbound HTTPS calls (ChromaDB ONNX model download, Bosch LLM Farm API).

### Additional complication
When `httpx.AsyncClient(verify=False)` was injected into `AzureChatOpenAI`, the LangChain agent still failed with `All connection attempts failed` because the async client was not picking up the proxy environment variables (`http_proxy=http://localhost:3128`).

### Fix applied
Patched SSL verification globally at the Python process entry point in [hermes/__main__.py](../hermes/__main__.py):

```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

This applies to all HTTP libraries (httpx, urllib3, requests, openai SDK) for the lifetime of the process.

### Production fix
The proper long-term fix is to configure Python to trust the corporate CA certificate:
```
SSL_CERT_FILE=C:\path\to\bosch-root-ca.crt
```
Ask IT/security for the Bosch root CA `.crt` file. Once set, the global SSL patch can be removed.

### Rules to carry forward
- ChromaDB's default embedding function downloads an ONNX model from the internet on first use — this will fail behind the corporate proxy. Always provide an explicit `embedding_function` to `KnowledgeService` to avoid this.
- The Bosch farm proxy runs on `localhost:3128`. Any new HTTP client created without inheriting environment variables will bypass the proxy and fail.
- When testing connectivity: a `httpx.ConnectError` with SSL failure is different from `All connection attempts failed` — the former is a certificate issue, the latter is a proxy/routing issue.

---

## LL-05 — MCP Server Entry Point

**Date:** 2026-04-08
**Error:** MCP server starts and exits immediately without error from VS Code.

### What happened
The VS Code `mcp.json` was configured as:
```json
"args": ["-m", "hermes.mcp_server"]
```
Running the module file directly (`-m hermes.mcp_server`) only defines the tool functions — there is no `if __name__ == "__main__"` block in `mcp_server.py`, so the process exits immediately.

### Fix applied
Changed to use the proper entry point with the `--mcp` flag:
```json
"args": ["-m", "hermes", "--mcp"]
```
This routes through `hermes/__main__.py` which calls `mcp.run(transport="stdio")`.

### Rules to carry forward
- The MCP server communicates via **stdin/stdout pipes** (`transport="stdio"`). Running it manually in a terminal with no piped input causes an immediate clean exit — this is correct behavior, not an error.
- VS Code starts and stops the MCP process automatically. You do not start it manually.
- Always use the full path to the venv Python in `mcp.json` — the system Python does not have the project's packages installed.

```json
"command": "c:\\Project Hermes\\.venv\\Scripts\\python.exe"
```
