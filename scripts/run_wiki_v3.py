"""Driver: re-run wiki query phase v3 against the EXISTING wiki + index.

The ONLY change vs v2 is the per-page truncation cap in
src.wiki_query.format_page_block (4000 -> 24000). Retrieval, embeddings, and the
vector index are unchanged, so this driver LOADS the existing persisted Chroma
collection instead of rebuilding it (honors "do not modify the embedding/index").

Reuses src.wiki_query.answer_question without modification (same prompt, model,
max_tokens=400, temperature=0.0, top-k=5). Output -> results/wiki_answers_v3.json.
v1 and v2 answer files are left untouched.

Run from project root: python -m scripts.run_wiki_v3
"""

from __future__ import annotations

import time

import chromadb

from src import config, utils, wiki_ingest, wiki_query


V3_OUTPUT_PATH = config.RESULTS_DIR / "wiki_answers_v3.json"
V3_PARTIAL_PATH = config.RESULTS_DIR / "_wiki_v3_partial.json"


def load_existing_collection():
    client = chromadb.PersistentClient(path=str(config.RAG_CHROMA_DIR))
    return client.get_collection(name=wiki_query.WIKI_VECTOR_COLLECTION)


def main() -> None:
    print("Phase v3: re-running LLM-Wiki answering (page cap 4000 -> 24000)", flush=True)

    collection = load_existing_collection()
    pages = wiki_ingest.list_existing_pages()
    print(f"Loaded existing index: {collection.count()} vectors, {len(pages)} pages.", flush=True)
    pages_by_path = {p["path"]: p for p in pages}

    questions = utils.read_json(config.BENCHMARK_QUESTIONS)

    if V3_PARTIAL_PATH.exists():
        answers = utils.read_json(V3_PARTIAL_PATH)
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
                r = wiki_query.answer_question(q["question"], collection, pages_by_path)
                if r["answer"]:
                    break
            except Exception as e:
                print(f"  q{qid} attempt {attempt + 1} error: {e!r}", flush=True)
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
            utils.append_progress(f"Wiki v3 q{qid} failed after 3 retries")

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
        utils.write_json(V3_PARTIAL_PATH, answers)

    utils.write_json(V3_OUTPUT_PATH, answers)
    if V3_PARTIAL_PATH.exists():
        V3_PARTIAL_PATH.unlink()

    print(f"\nv3 complete: wrote {len(answers)} answers to {V3_OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
