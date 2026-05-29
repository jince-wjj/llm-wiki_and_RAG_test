"""Phase 5.2: answer benchmark questions using the LLM-Wiki.

Retrieval pipeline (section 5.2):
  1. Extract candidate entities from the question via a cheap LLM call.
  2. Map each candidate to a wiki page (exact or fuzzy match on name/aliases).
  3. Also do a BGE-M3 vector search over wiki page "headers" (frontmatter +
     first 500 chars of body), one vector per page.
  4. Merge results, dedupe by path, take top-5 pages.
  5. Send full page contents to DeepSeek with the strict prompt.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import chromadb

from . import api_client, config, utils, wiki_ingest


TOP_K_PAGES = 5
ENTITY_TOP_PAGES = 3  # max pages per matched entity
VECTOR_TOP_PAGES = 5  # max pages from vector search
PAGE_HEADER_CHARS = 500  # first N chars of body used as 'header'
WIKI_VECTOR_COLLECTION = "wiki_pages_v1"


ENTITY_EXTRACTION_PROMPT = """给定一个红楼梦相关的问题,请抽取出问题中提到的所有具体实体(人物、地点、事件、概念)。

问题: {QUESTION}

仅输出 JSON,无任何额外文字:
{{
  "entities": ["实体1", "实体2", ...]
}}
"""


WIKI_ANSWER_PROMPT = """你是红楼梦研究者。根据以下结构化 wiki 页面回答问题。如果页面不足以回答,如实说"wiki 未提供足够信息"。

Wiki 页面:
{PAGE_BLOCKS}

问题: {QUESTION}

答案(不超过200字):"""


def extract_entities(question: str) -> list[str]:
    """Cheap LLM call to extract entities. Falls back to [] on failure."""
    try:
        parsed, _ = api_client.chat_complete_json(
            messages=[
                {
                    "role": "system",
                    "content": "你是命名实体抽取器,只输出严格 JSON。",
                },
                {"role": "user", "content": ENTITY_EXTRACTION_PROMPT.format(QUESTION=question)},
            ],
            phase="wiki_query",
            temperature=0.0,
            max_tokens=256,
        )
        ents = parsed.get("entities") or []
        return [e.strip() for e in ents if isinstance(e, str) and e.strip()]
    except Exception:
        return []


def find_page_for_entity(entity: str, pages: list[dict]) -> list[dict]:
    """Match an entity name against wiki pages. Returns ranked candidates."""
    matches: list[tuple[int, dict]] = []
    for p in pages:
        score = 0
        if entity == p["name"]:
            score += 100
        if entity in p["name"] or p["name"] in entity:
            score += 30
        for alias in p.get("aliases") or []:
            if isinstance(alias, str):
                if entity == alias:
                    score += 80
                elif entity in alias or alias in entity:
                    score += 20
        if score > 0:
            matches.append((score, p))
    matches.sort(key=lambda x: -x[0])
    return [m[1] for m in matches[:ENTITY_TOP_PAGES]]


def page_header_text(page: dict) -> str:
    """Build the 'header' text used to index a wiki page in the vector store.
    It includes frontmatter (which has type/name/aliases) and the first N chars
    of body content.
    """
    fm = page.get("frontmatter") or {}
    name = fm.get("name") or page["name"]
    aliases = fm.get("aliases") or []
    type_ = fm.get("type") or page["type"]
    head = f"{type_} · {name}"
    if aliases:
        head += f" · 别名: {', '.join(aliases) if isinstance(aliases, list) else aliases}"
    body = (page.get("body") or "").strip()
    if len(body) > PAGE_HEADER_CHARS:
        body = body[:PAGE_HEADER_CHARS]
    return head + "\n" + body


def build_wiki_vector_index() -> tuple[Any, list[dict]]:
    """Build (or rebuild) the wiki page vector index in Chroma.

    Returns (collection, all_pages). Uses BGE-M3 embeddings over each page's
    'header' text (defined above).
    """
    config.RAG_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config.RAG_CHROMA_DIR))
    # Drop any prior version to ensure freshness with current wiki state
    try:
        client.delete_collection(name=WIKI_VECTOR_COLLECTION)
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=WIKI_VECTOR_COLLECTION,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,
    )

    pages = wiki_ingest.list_existing_pages()
    if not pages:
        return collection, pages

    headers = [page_header_text(p) for p in pages]
    ids = [p["path"] for p in pages]
    metas = [{"path": p["path"], "type": p["type"], "name": p["name"]} for p in pages]

    # Batch embed (BGE-M3 SiliconFlow batch size 16)
    BATCH = 16
    for start in range(0, len(headers), BATCH):
        chunk = headers[start : start + BATCH]
        vecs = api_client.embed(chunk, phase="wiki_query")
        collection.upsert(
            ids=ids[start : start + BATCH],
            embeddings=vecs,
            metadatas=metas[start : start + BATCH],
            documents=chunk,
        )
    return collection, pages


def vector_search_wiki(collection, query: str, k: int = VECTOR_TOP_PAGES) -> list[str]:
    """Return list of page paths."""
    qvec = api_client.embed([query], phase="wiki_query")[0]
    res = collection.query(query_embeddings=[qvec], n_results=k)
    return res["ids"][0] if res["ids"] else []


def format_page_block(page: dict, max_chars: int = 24000) -> str:
    text = page.get("full_text") or ""
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[... 页面较长,已截断 ...]"
    return f"--- 页面: {page['path']} ---\n{text}"


def answer_question(
    question: str, collection, pages_by_path: dict[str, dict]
) -> dict:
    """End-to-end wiki retrieval + answer for one question."""
    selected_paths: list[str] = []

    # 1. Entity-based lookup
    entities = extract_entities(question)
    for ent in entities:
        for cand in find_page_for_entity(ent, list(pages_by_path.values())):
            if cand["path"] not in selected_paths:
                selected_paths.append(cand["path"])

    # 2. Vector search over wiki page headers
    vec_hits = vector_search_wiki(collection, question, k=VECTOR_TOP_PAGES)
    for path in vec_hits:
        if path not in selected_paths:
            selected_paths.append(path)

    # 3. Cap at TOP_K_PAGES (preserve order: entity-matched first, then vector)
    selected_paths = selected_paths[:TOP_K_PAGES]

    selected_pages = [pages_by_path[p] for p in selected_paths if p in pages_by_path]

    if not selected_pages:
        # No pages found at all — answer will probably say "wiki 未提供足够信息"
        pages_block = "(未检索到相关 wiki 页面)"
    else:
        pages_block = "\n\n".join(format_page_block(p) for p in selected_pages)

    prompt = WIKI_ANSWER_PROMPT.format(PAGE_BLOCKS=pages_block, QUESTION=question)
    res = api_client.chat_complete(
        messages=[
            {
                "role": "system",
                "content": "你是中国古典文学研究者,严格依据 wiki 页面回答问题。",
            },
            {"role": "user", "content": prompt},
        ],
        phase="wiki_query",
        temperature=0.0,
        max_tokens=400,
    )
    return {
        "answer": res["content"].strip(),
        "retrieved_page_paths": selected_paths,
        "entities_extracted": entities,
        "input_tokens": res["input_tokens"],
        "output_tokens": res["output_tokens"],
        "latency_ms": res["latency_ms"],
    }


def run() -> None:
    if not utils.checkpoint_exists("phase3_done"):
        print("Phase 3 not complete — refusing to run wiki query.", file=sys.stderr)
        sys.exit(2)

    print("Phase 5.2: LLM-Wiki answering", flush=True)
    utils.append_progress("Phase 5.2 started: LLM-Wiki answering")

    # Build wiki vector index (once)
    print("Building wiki vector index...", flush=True)
    collection, pages = build_wiki_vector_index()
    print(f"Indexed {len(pages)} wiki pages.", flush=True)
    pages_by_path = {p["path"]: p for p in pages}

    questions = utils.read_json(config.BENCHMARK_QUESTIONS)

    partial_path = config.RESULTS_DIR / "_wiki_partial.json"
    if partial_path.exists():
        answers = utils.read_json(partial_path)
        done_ids = {a["question_id"] for a in answers}
        print(f"Resuming. Already done: {len(done_ids)}", flush=True)
    else:
        answers = []
        done_ids = set()

    for q in questions:
        qid = q["id"]
        if qid in done_ids:
            continue
        for attempt in range(3):
            try:
                r = answer_question(q["question"], collection, pages_by_path)
                if r["answer"]:
                    break
            except Exception as e:
                print(f"  q{qid} attempt {attempt+1} error: {e!r}", flush=True)
                time.sleep(2)
        else:
            r = {
                "answer": "",
                "retrieved_page_paths": [],
                "entities_extracted": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
            }
            utils.append_progress(f"Wiki q{qid} failed after 3 retries")

        answers.append(
            {
                "question_id": qid,
                "question": q["question"],
                "tier": q["tier"],
                "answer": r["answer"],
                "retrieved_page_paths": r["retrieved_page_paths"],
                "entities_extracted": r["entities_extracted"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "latency_ms": r["latency_ms"],
            }
        )
        if qid % 5 == 0 or qid == len(questions):
            print(
                f"  q{qid:3d} [{q['tier']}] {len(r['answer'])}c answered "
                f"pages={len(r['retrieved_page_paths'])} "
                f"({r['input_tokens']}+{r['output_tokens']} tk, {r['latency_ms']}ms)",
                flush=True,
            )
        utils.write_json(partial_path, answers)

    utils.write_json(config.WIKI_ANSWERS_JSON, answers)
    if partial_path.exists():
        partial_path.unlink()

    print(f"Phase 5.2 complete: wrote {len(answers)} wiki answers", flush=True)


if __name__ == "__main__":
    run()
