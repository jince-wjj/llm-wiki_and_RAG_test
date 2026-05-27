"""Phase 4: build the vanilla RAG baseline.

Chunking: 500-char sliding windows with 100-char overlap. Each chunk gets
{chunk_id, chapter_id, position, char_count} metadata.

Embedding: BAAI/bge-m3 via SiliconFlow, batches of 16.

Storage: ChromaDB persistent at rag_baseline/chroma_db/ in a single
collection named 'hongloumeng_chunks'.

Verification: a simple lookup confirms top-5 retrieval works for
"林黛玉的性格是怎样的".
"""

from __future__ import annotations

import json
import os
import sys
from typing import Iterable

import chromadb

from . import api_client, config, utils


CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
EMBED_BATCH = 16
COLLECTION_NAME = "hongloumeng_chunks"


def chunk_chapter(chapter_id: int, text: str) -> list[dict]:
    """Slide a 500-char window across `text` with 100-char overlap.

    Returns dicts with chunk_id, chapter_id, position (window start), char_count, text.
    """
    chunks: list[dict] = []
    n = len(text)
    step = CHUNK_SIZE - CHUNK_OVERLAP  # = 400 by default
    if n <= CHUNK_SIZE:
        chunks.append(
            {
                "chunk_id": f"ch{chapter_id:03d}_p000000",
                "chapter_id": chapter_id,
                "position": 0,
                "char_count": n,
                "text": text,
            }
        )
        return chunks
    pos = 0
    idx = 0
    while pos < n:
        end = min(pos + CHUNK_SIZE, n)
        snippet = text[pos:end]
        if snippet.strip():
            chunks.append(
                {
                    "chunk_id": f"ch{chapter_id:03d}_p{pos:06d}",
                    "chapter_id": chapter_id,
                    "position": pos,
                    "char_count": len(snippet),
                    "text": snippet,
                }
            )
        if end >= n:
            break
        pos += step
        idx += 1
    return chunks


def write_chunks_jsonl(chunks: list[dict]) -> None:
    """Persist chunks to chunks.jsonl, one per line."""
    config.RAG_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.RAG_CHUNKS_JSONL, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def load_chunks_jsonl() -> list[dict]:
    chunks: list[dict] = []
    with open(config.RAG_CHUNKS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunks.append(json.loads(line))
    return chunks


def get_collection():
    """Open (or create) the Chroma collection. We supply our own embeddings,
    so the embedding_function is set to None and Chroma stores vectors
    verbatim."""
    config.RAG_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.RAG_CHROMA_DIR))
    # Use cosine distance which is conventional for sentence/passage embeddings
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )


def embed_and_store(chunks: list[dict], batch_size: int = EMBED_BATCH) -> int:
    """Embed each chunk with BGE-M3 and upsert into Chroma. Returns count stored."""
    collection = get_collection()
    n = len(chunks)
    stored = 0

    for start in range(0, n, batch_size):
        batch = chunks[start : start + batch_size]
        texts = [c["text"] for c in batch]
        vectors = api_client.embed(texts, phase="rag_ingest")
        ids = [c["chunk_id"] for c in batch]
        metas = [
            {
                "chapter_id": c["chapter_id"],
                "position": c["position"],
                "char_count": c["char_count"],
            }
            for c in batch
        ]
        documents = texts
        collection.upsert(
            ids=ids,
            embeddings=vectors,
            metadatas=metas,
            documents=documents,
        )
        stored += len(batch)
        if stored % 100 == 0 or stored == n:
            print(f"  embedded {stored}/{n}", flush=True)
    return stored


def smoke_test_query() -> dict:
    """Embed one query and retrieve top-5 chunks. Used for the README check."""
    q = "林黛玉的性格是怎样的"
    qvec = api_client.embed([q], phase="rag_ingest")[0]
    collection = get_collection()
    res = collection.query(query_embeddings=[qvec], n_results=5)
    ids = res["ids"][0]
    metas = res["metadatas"][0]
    docs = res["documents"][0]
    return {
        "query": q,
        "top5": [
            {"id": ids[i], "chapter": metas[i]["chapter_id"], "snippet": docs[i][:80]}
            for i in range(len(ids))
        ],
    }


def write_baseline_readme(n_chunks: int, sample: dict) -> None:
    rd = config.RAG_DIR / "README.md"
    lines = [
        "# RAG Baseline",
        "",
        "This directory holds the **vanilla** RAG baseline used for comparison",
        "against the LLM-Wiki paradigm.",
        "",
        "## Configuration",
        "",
        f"- Chunk size: {CHUNK_SIZE} Chinese characters (sliding window)",
        f"- Overlap: {CHUNK_OVERLAP} characters between adjacent chunks",
        f"- Embedding model: `{config.MODEL_EMBEDDING}` via SiliconFlow",
        f"- Vector store: ChromaDB persistent at `rag_baseline/chroma_db/`",
        f"- Collection: `{COLLECTION_NAME}` (cosine distance)",
        f"- Total chunks indexed: **{n_chunks}**",
        "",
        "## Files",
        "",
        "- `chunks.jsonl` — all chunks with metadata (committed)",
        "- `chroma_db/` — binary index (gitignored; regenerable from chunks.jsonl)",
        "- `README.md` — this file",
        "",
        "## Smoke test",
        "",
        f"Query: `{sample['query']}`",
        "",
        "Top-5 chunks retrieved (by cosine distance):",
        "",
    ]
    for hit in sample["top5"]:
        lines.append(f"- `{hit['id']}` (第{hit['chapter']}回): {hit['snippet']}...")
    lines.append("")
    with open(rd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run() -> None:
    if not utils.checkpoint_exists("phase3_done"):
        print("Phase 3 not complete — refusing to run Phase 4.", file=sys.stderr)
        sys.exit(2)

    print("Phase 4: build RAG baseline", flush=True)
    utils.append_progress("Phase 4 started: RAG baseline build")

    # Step 1: chunk all chapters
    all_chunks: list[dict] = []
    for ch in range(1, 81):
        with open(config.RAW_CHAPTERS_DIR / f"{ch:03d}.txt", "r", encoding="utf-8") as f:
            body = f.read()
        all_chunks.extend(chunk_chapter(ch, body))
    print(f"Chunked into {len(all_chunks)} chunks", flush=True)
    write_chunks_jsonl(all_chunks)

    if not (1500 <= len(all_chunks) <= 2500):
        utils.append_progress(
            f"WARN: chunk count {len(all_chunks)} outside 1500-2500 (continuing)"
        )

    # Step 2: embed + store
    stored = embed_and_store(all_chunks)
    print(f"Stored {stored} embeddings in Chroma", flush=True)

    # Step 3: smoke test
    sample = smoke_test_query()
    print("Smoke test top-5:", flush=True)
    for hit in sample["top5"]:
        print(f"  {hit['id']} (第{hit['chapter']}回): {hit['snippet']}...", flush=True)
    write_baseline_readme(len(all_chunks), sample)

    utils.write_checkpoint(
        "phase4_done",
        {
            "n_chunks": len(all_chunks),
            "chunk_size": CHUNK_SIZE,
            "overlap": CHUNK_OVERLAP,
            "embedding_model": config.MODEL_EMBEDDING,
        },
    )
    utils.add_phase_complete("phase4")
    utils.append_progress(
        f"Phase 4 complete: {len(all_chunks)} chunks embedded and indexed"
    )


if __name__ == "__main__":
    run()
