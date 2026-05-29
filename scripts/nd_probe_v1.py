"""Diagnostic: reproduce v1's answers for the 5 newly-introduced-refusal questions.

For each question, reconstruct v1's EXACT 5-page context from the pre-merge git state
(HEAD~1), then call the answer model 3x at temperature=0.0 / max_tokens=400 with the
same prompt/system used by src.wiki_query. Records refusal status per rep.

Purpose: determine whether v1's non-refusals on Q48/59/64/84/91 were reproducible (so
the v2 refusal is a genuine merge-caused regression) or themselves fragile (noise).

Reads pages via `git show HEAD~1:<path>` so deleted dupe files are recoverable. Does
NOT modify any tracked file or the official results. Output -> /tmp/wiki_merge/nd_probe_v1.json.

Run from project root: python -m scripts.nd_probe_v1
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from src import api_client, config, utils, wiki_ingest, wiki_query

REF = re.compile(r"wiki\s*未提供足够信息")
REPS = 3
PROBE_IDS = [48, 59, 64, 84, 91]
OUT = Path("/tmp/wiki_merge/nd_probe_v1.json")


def git_show(rel_path: str) -> str | None:
    """Return file content at HEAD~1, or None if absent."""
    r = subprocess.run(
        ["git", "show", f"HEAD~1:wiki/{rel_path}"],
        cwd=config.PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    return r.stdout if r.returncode == 0 else None


def page_from_text(rel_path: str, text: str) -> dict:
    meta, body = wiki_ingest.parse_frontmatter(text)
    return {
        "path": rel_path,
        "type": rel_path.split("/")[0],
        "name": meta.get("name") or Path(rel_path).stem,
        "aliases": meta.get("aliases") or [],
        "frontmatter": meta,
        "body": body,
        "full_text": text,
    }


def build_prompt(question: str, pages: list[dict]) -> str:
    block = "\n\n".join(wiki_query.format_page_block(p) for p in pages) if pages else "(未检索到相关 wiki 页面)"
    return wiki_query.WIKI_ANSWER_PROMPT.format(PAGE_BLOCKS=block, QUESTION=question)


def main() -> None:
    v1 = {a["question_id"]: a for a in utils.read_json(config.WIKI_ANSWERS_JSON)}

    results = []
    for qid in PROBE_IDS:
        a = v1[qid]
        paths = a["retrieved_page_paths"]
        pages = []
        missing = []
        for p in paths:
            txt = git_show(p)
            if txt is None:
                missing.append(p)
                continue
            pages.append(page_from_text(p, txt))
        prompt = build_prompt(a["question"], pages)
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
        results.append(
            {
                "qid": qid,
                "v1_original_refused": bool(REF.search(a["answer"])),
                "reconstructed_pages": [p["path"] for p in pages],
                "missing_pages": missing,
                "rep_refusals": refusals,
                "reps": REPS,
                "rep_detail": reps,
            }
        )
        print(f"Q{qid}: v1_orig_refused={bool(REF.search(a['answer']))} "
              f"reconstructed_rep_refusals={refusals}/{REPS} missing={missing}")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {OUT}")
    print("Interpretation: if rep_refusals==0/3, v1 reproducibly ANSWERED -> v2 refusal is a "
          "genuine merge-caused regression. If 3/3, v1 also refuses on rerun -> original v1 "
          "non-refusal was noise.")


if __name__ == "__main__":
    main()
