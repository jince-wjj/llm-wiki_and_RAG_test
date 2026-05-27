"""Phase 5.1: answer benchmark questions using the RAG baseline.

For each question:
  1. Embed the question with BGE-M3.
  2. Retrieve top-5 chunks from ChromaDB.
  3. Build the strict answer prompt (section 5.1).
  4. Call DeepSeek (temperature=0.0, max_tokens=400).
  5. Record answer + retrieved_chunk_ids + tokens + latency.

Output: results/rag_answers.json (100 entries).
"""

from __future__ import annotations

import sys
import time
from typing import Any

from . import api_client, config, rag_ingest, utils


TOP_K = 5

RAG_ANSWER_PROMPT = """你是红楼梦研究者。根据以下原文片段回答问题。如果片段不足以回答,如实说"原文未提供足够信息"。

原文片段:
{SNIPPETS}

问题: {QUESTION}

答案(不超过200字):"""


def format_snippets(retrieved: list[dict]) -> str:
    """Build the '[片段N, 来自第X回] body' lines."""
    parts = []
    for i, h in enumerate(retrieved, 1):
        parts.append(f"[片段{i}, 来自第{h['chapter_id']}回]\n{h['text']}")
    return "\n\n".join(parts)


def retrieve_top_k(question: str, collection, k: int = TOP_K) -> list[dict]:
    qvec = api_client.embed([question], phase="rag_query")[0]
    res = collection.query(query_embeddings=[qvec], n_results=k)
    ids = res["ids"][0]
    metas = res["metadatas"][0]
    docs = res["documents"][0]
    return [
        {
            "chunk_id": ids[i],
            "chapter_id": metas[i]["chapter_id"],
            "text": docs[i],
        }
        for i in range(len(ids))
    ]


def answer_question(question: str, collection) -> dict:
    retrieved = retrieve_top_k(question, collection, k=TOP_K)
    prompt = RAG_ANSWER_PROMPT.format(
        SNIPPETS=format_snippets(retrieved),
        QUESTION=question,
    )
    res = api_client.chat_complete(
        messages=[
            {
                "role": "system",
                "content": "你是中国古典文学研究者,严格依据原文回答问题。",
            },
            {"role": "user", "content": prompt},
        ],
        phase="rag_query",
        temperature=0.0,
        max_tokens=400,
    )
    return {
        "answer": res["content"].strip(),
        "retrieved_chunk_ids": [r["chunk_id"] for r in retrieved],
        "retrieved_chapter_ids": [r["chapter_id"] for r in retrieved],
        "input_tokens": res["input_tokens"],
        "output_tokens": res["output_tokens"],
        "latency_ms": res["latency_ms"],
    }


def run() -> None:
    if not utils.checkpoint_exists("phase4_done"):
        print("Phase 4 not complete — refusing to run RAG query.", file=sys.stderr)
        sys.exit(2)

    print("Phase 5.1: RAG baseline answering", flush=True)
    utils.append_progress("Phase 5.1 started: RAG baseline answering")

    questions = utils.read_json(config.BENCHMARK_QUESTIONS)
    if len(questions) != 100:
        print(
            f"WARN: expected 100 questions, found {len(questions)}",
            file=sys.stderr,
            flush=True,
        )

    collection = rag_ingest.get_collection()

    # Resume support
    partial_path = config.RESULTS_DIR / "_rag_partial.json"
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
                r = answer_question(q["question"], collection)
                if r["answer"]:
                    break
            except Exception as e:
                print(f"  q{qid} attempt {attempt+1} error: {e!r}", flush=True)
                time.sleep(2)
        else:
            r = {
                "answer": "",
                "retrieved_chunk_ids": [],
                "retrieved_chapter_ids": [],
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
            }
            utils.append_progress(f"RAG q{qid} failed after 3 retries")

        answers.append(
            {
                "question_id": qid,
                "question": q["question"],
                "tier": q["tier"],
                "answer": r["answer"],
                "retrieved_chunk_ids": r["retrieved_chunk_ids"],
                "retrieved_chapter_ids": r["retrieved_chapter_ids"],
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
                "latency_ms": r["latency_ms"],
            }
        )
        if qid % 5 == 0 or qid == len(questions):
            print(
                f"  q{qid:3d} [{q['tier']}] {len(r['answer'])}c answered "
                f"({r['input_tokens']}+{r['output_tokens']} tk, {r['latency_ms']}ms)",
                flush=True,
            )
        utils.write_json(partial_path, answers)

    utils.write_json(config.RAG_ANSWERS_JSON, answers)
    if partial_path.exists():
        partial_path.unlink()

    print(f"Phase 5.1 complete: wrote {len(answers)} RAG answers", flush=True)


if __name__ == "__main__":
    run()
