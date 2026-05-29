"""Diagnostic: measure DeepSeek-V3 generation nondeterminism at temperature=0.

For a set of question IDs, FREEZE the v2 retrieved_page_paths (so retrieval is held
constant) and re-call the answer model N times with the EXACT same prompt / system /
temperature=0.0 / max_tokens=400 used by src.wiki_query. Record the refusal status of
each repetition.

This isolates pure answer-generation nondeterminism — it does NOT touch retrieval,
the merge, or the official v2 results. Output -> /tmp/wiki_merge/nd_probe.json.

Run from project root: python -m scripts.nd_probe
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src import api_client, config, utils, wiki_ingest, wiki_query

REF = re.compile(r"wiki\s*未提供足够信息")
REPS = 3
# 5 newly-introduced refusals + 6 reversed refusals + a few stable-answer controls
PROBE_IDS = [48, 59, 64, 84, 91, 5, 24, 30, 40, 85, 94, 1, 4, 8]
OUT = Path("/tmp/wiki_merge/nd_probe.json")


def build_prompt(question: str, pages: list[dict]) -> str:
    if not pages:
        block = "(未检索到相关 wiki 页面)"
    else:
        block = "\n\n".join(wiki_query.format_page_block(p) for p in pages)
    return wiki_query.WIKI_ANSWER_PROMPT.format(PAGE_BLOCKS=block, QUESTION=question)


def main() -> None:
    v2 = {a["question_id"]: a for a in utils.read_json(config.RESULTS_DIR / "wiki_answers_v2.json")}
    pages_by_path = {p["path"]: p for p in wiki_ingest.list_existing_pages()}

    results = []
    for qid in PROBE_IDS:
        a = v2[qid]
        frozen_paths = a["retrieved_page_paths"]
        sel = [pages_by_path[p] for p in frozen_paths if p in pages_by_path]
        prompt = build_prompt(a["question"], sel)
        reps = []
        for _ in range(REPS):
            r = api_client.chat_complete(
                messages=[
                    {"role": "system", "content": "你是中国古典文学研究者,严格依据 wiki 页面回答问题。"},
                    {"role": "user", "content": prompt},
                ],
                phase="wiki_query",
                temperature=0.0,
                max_tokens=400,
            )
            ans = r["content"].strip()
            reps.append({"refused": bool(REF.search(ans)), "len": len(ans), "answer": ans})
        refusals = sum(1 for x in reps if x["refused"])
        flipped = 0 < refusals < REPS  # mixed across reps == nondeterministic on refusal
        results.append(
            {
                "qid": qid,
                "v2_refused": bool(REF.search(a["answer"])),
                "rep_refusals": refusals,
                "reps": REPS,
                "refusal_flips_across_reps": flipped,
                "rep_detail": reps,
            }
        )
        print(f"Q{qid}: v2_refused={bool(REF.search(a['answer']))} "
              f"rep_refusals={refusals}/{REPS} flip={flipped}")

    flip_count = sum(1 for r in results if r["refusal_flips_across_reps"])
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{flip_count}/{len(results)} probed questions had refusal status FLIP across "
          f"identical-input reps (pure temp=0 nondeterminism).")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
