"""Driver: re-run wiki query phase against post-merge wiki, write to wiki_answers_v2.json.

Reuses src.wiki_query functions (entity extraction, vector search, answer prompt) — does NOT
modify them. Writes output to results/wiki_answers_v2.json. The original
results/wiki_answers.json is left untouched.

The wiki vector index is rebuilt from scratch (build_wiki_vector_index drops the prior
collection). max_tokens, temperature, top-k, and the answer model are inherited from
src.wiki_query without modification.

Run from project root: python -m scripts.run_wiki_v2
"""

from __future__ import annotations

import time

from src import config, utils, wiki_query


V2_OUTPUT_PATH = config.RESULTS_DIR / "wiki_answers_v2.json"
V2_PARTIAL_PATH = config.RESULTS_DIR / "_wiki_v2_partial.json"


def main() -> None:
    print("Phase v2: re-running LLM-Wiki answering against merged wiki", flush=True)

    print("Rebuilding wiki vector index from scratch...", flush=True)
    collection, pages = wiki_query.build_wiki_vector_index()
    print(f"Indexed {len(pages)} wiki pages.", flush=True)
    pages_by_path = {p["path"]: p for p in pages}

    questions = utils.read_json(config.BENCHMARK_QUESTIONS)

    if V2_PARTIAL_PATH.exists():
        answers = utils.read_json(V2_PARTIAL_PATH)
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
            utils.append_progress(f"Wiki v2 q{qid} failed after 3 retries")

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
        utils.write_json(V2_PARTIAL_PATH, answers)

    utils.write_json(V2_OUTPUT_PATH, answers)
    if V2_PARTIAL_PATH.exists():
        V2_PARTIAL_PATH.unlink()

    print(f"\nv2 complete: wrote {len(answers)} answers to {V2_OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
