import os
import hashlib
import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings
from openai import AzureOpenAI

AZURE_ENDPOINT = "https://YOUR_AZURE_OPENAI_ENDPOINT"
API_VERSION = "2024-08-01-preview"
CHAT_DEPLOYMENT = "gpt-4o-mini"
EMBED_DEPLOYMENT = "text-embedding-3-small"

# ── Switch embeddings ────────────────────────────────────────────────────────
# Set to True  → real semantic embeddings via Azure OpenAI (requires API key)
# Set to False → local hash-based embeddings, no network call needed
USE_FARM_EMBEDDINGS = True
# ─────────────────────────────────────────────────────────────────────────────


class _LocalEmbedFn(EmbeddingFunction):
    """Hash-based embedding — no internet required. Good enough for offline checks."""
    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        # sha256 → 64 hex chars; take 32 pairs → 32-dim float vector
        return [
            [float(int(hashlib.sha256(doc.encode()).hexdigest()[i:i+2], 16)) / 255.0
             for i in range(0, 64, 2)]
            for doc in input
        ]


class _AzureEmbedFn(EmbeddingFunction):
    """Calls the Azure OpenAI embeddings endpoint (e.g. text-embedding-3-small)."""
    def __init__(self, api_key: str) -> None:
        self._client = AzureOpenAI(
            azure_endpoint=AZURE_ENDPOINT,
            api_version=API_VERSION,
            api_key=api_key,
        )

    def __call__(self, input: Documents) -> Embeddings:
        response = self._client.embeddings.create(
            model=EMBED_DEPLOYMENT,
            input=list(input),
        )
        return [item.embedding for item in response.data]


api_key = os.environ["AZURE_OPENAI_API_KEY"]

embed_fn = _AzureEmbedFn(api_key) if USE_FARM_EMBEDDINGS else _LocalEmbedFn()

client = chromadb.EphemeralClient()
collection = client.create_collection("test", embedding_function=embed_fn)
collection.add(ids=["1","2"], documents=[
    "Python lists are ordered",
    "Dicts store key-value pairs"
])

# Step 1: Retrieve relevant chunks
results = collection.query(query_texts=["how do I store ordered items?"], n_results=2)
chunks = results["documents"][0]

# Step 2: Build prompt with context
context = "\n\n".join(chunks)
prompt = f"Answer based ONLY on this context:\n\n{context}\n\nQuestion: How do I store ordered items in Python?"

# Step 3: Call LLM via Azure OpenAI
llm = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_version=API_VERSION,
    api_key=api_key,
)

response = llm.chat.completions.create(
    model=CHAT_DEPLOYMENT,
    messages=[{"role": "user", "content": prompt}]
)
print(response.choices[0].message.content)