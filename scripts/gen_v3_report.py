"""Generate results/wiki_v3_comparison.md (run after scripts/run_wiki_v3.py).

Sections: (1) the fix, (2) regression recovery for Q59/Q84/Q91,
(3) fragmentation casualties Q38/Q65/Q97, (4) refusal counts v1/v2/v3,
(5) nondeterminism caveat.

Run from project root: python -m scripts.gen_v3_report
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
V1 = PROJ / "results/wiki_answers.json"
V2 = PROJ / "results/wiki_answers_v2.json"
V3 = PROJ / "results/wiki_answers_v3.json"
USAGE_BEFORE = Path("/tmp/wiki_merge/usage_before_v3.json")
USAGE_NOW = PROJ / "usage.json"
REPORT = PROJ / "results/wiki_v3_comparison.md"

REF = re.compile(r"wiki\s*未提供足够信息")
CITE = re.compile(r"\[第.+?回\]|（第.+?回）|第\d+回")  # a chapter citation => substantive content present
OLD_CAP = 4000
NEW_CAP = 24000
LARGEST_PAGE = ("人物/贾宝玉.md", 21039)
# From the calibrated overflow check (cap=24000, conservative ratio):
MAX_PROMPT_CHARS = 46071
MAX_PROMPT_TOK_CONS = 33471
MAX_PROMPT_TOK_MED = 31791
MAX_PROMPT_QID = 75

REGRESSION_IDS = [59, 84, 91]
CASUALTY_IDS = [38, 65, 97]


def refused(a: str) -> bool:
    """Strict: answer contains the refusal phrase (may still carry partial substantive content)."""
    return bool(REF.search(a or ""))


def pure_refused(a: str) -> bool:
    """Refusal phrase present AND no chapter citation => essentially no substantive content."""
    return bool(REF.search(a or "")) and not bool(CITE.search(a or ""))


# Manual adjudication of the 3 v2 regressions, based on close reading of the v3 answers.
REGRESSION_VERDICTS = {
    59: (
        "RECOVERED",
        "v3 returns the exact line (“你又干这些事了…”). The quote lives in 贾宝玉.md's 第19回 "
        "section, which sat *past* the old 4000-char cap (贾宝玉.md is 21K chars). So Q59 was a "
        "truncation casualty too — correcting the v2 report, which had attributed it to the "
        "甄宝玉 distractor alone.",
    ),
    84: (
        "RECOVERED (partial)",
        "The previously-truncated 第67回 line is back: v3 correctly states 宝钗 distributed the "
        "gifts with 黛玉's share doubled (（第67回）). It only notes 黛玉's *reaction* as missing — "
        "which is genuinely absent from the wiki, not a truncation effect. This is exactly v1's "
        "partial-answer behavior, so the truncation regression is reversed. (The strict refusal "
        "regex still flags it because the phrase appears for the unanswerable sub-part; it is "
        "**not** a pure refusal.)",
    ),
    91: (
        "STILL_REFUSING (expected, out of scope)",
        "Not truncation: 薛宝钗/秦可卿 pages are now fully included, but the question needs 第8回 "
        "秦可卿 origin content (养生堂 abandoned-child detail) that was never ingested onto any "
        "retrieved page. v3 supplies 第5回/第10回 facts but cannot confirm the contradiction. A "
        "content-gap / ingest issue, not the page cap.",
    ),
}


def md_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", "<br>") or "*(empty)*"


def main() -> None:
    v1 = {a["question_id"]: a for a in json.loads(V1.read_text(encoding="utf-8"))}
    v2 = {a["question_id"]: a for a in json.loads(V2.read_text(encoding="utf-8"))}
    v3 = {a["question_id"]: a for a in json.loads(V3.read_text(encoding="utf-8"))}

    usage_before = json.loads(USAGE_BEFORE.read_text(encoding="utf-8"))
    usage_now = json.loads(USAGE_NOW.read_text(encoding="utf-8"))
    d_cost = (
        usage_now["by_phase"]["wiki_query"]["cost_usd"]
        - usage_before["by_phase"]["wiki_query"]["cost_usd"]
    )
    d_total = usage_now["estimated_cost_usd"] - usage_before["estimated_cost_usd"]
    d_calls = usage_now["by_phase"]["wiki_query"]["calls"] - usage_before["by_phase"]["wiki_query"]["calls"]
    d_in = usage_now["by_phase"]["wiki_query"]["input_tokens"] - usage_before["by_phase"]["wiki_query"]["input_tokens"]
    d_out = usage_now["by_phase"]["wiki_query"]["output_tokens"] - usage_before["by_phase"]["wiki_query"]["output_tokens"]

    v1_ref = sum(1 for a in v1.values() if refused(a["answer"]))
    v2_ref = sum(1 for a in v2.values() if refused(a["answer"]))
    v3_ref = sum(1 for a in v3.values() if refused(a["answer"]))
    v1_pure = sum(1 for a in v1.values() if pure_refused(a["answer"]))
    v2_pure = sum(1 for a in v2.values() if pure_refused(a["answer"]))
    v3_pure = sum(1 for a in v3.values() if pure_refused(a["answer"]))

    L = []
    L += [
        "# Wiki v3 Comparison Report",
        "",
        "v3 changes exactly one thing vs v2: the per-page truncation cap in "
        "`src/wiki_query.py::format_page_block` (**4000 → 24000 chars**). Everything else is "
        "unchanged — same merged 438-page wiki, same BGE-M3 vector index (loaded, not rebuilt), "
        "same answer model (`deepseek-chat`/DeepSeek-V3), prompt, `max_tokens=400`, "
        "`temperature=0.0`, `top-k=5`. RAG side untouched. v1/v2 answer files preserved.",
        "",
    ]

    # ---- 1. The fix ----
    L += [
        "## 1. The Fix",
        "",
        f"- **Old per-page cap:** {OLD_CAP} chars",
        f"- **New per-page cap:** {NEW_CAP} chars",
        f"- **Largest merged page:** `{LARGEST_PAGE[0]}` at **{LARGEST_PAGE[1]:,} chars** — now "
        f"fully included (cap {NEW_CAP:,} leaves ~{NEW_CAP - LARGEST_PAGE[1]:,} chars headroom). "
        "Only one page (贾宝玉) exceeded the 16000 floor, so the cap was raised above it.",
        f"- **Max total prompt after change:** Q{MAX_PROMPT_QID} at {MAX_PROMPT_CHARS:,} chars ≈ "
        f"**{MAX_PROMPT_TOK_MED:,} tok** (median ratio) / **{MAX_PROMPT_TOK_CONS:,} tok** "
        "(conservative). DeepSeek-V3 context ≈ 64K tok; 55K stop-threshold **not approached** "
        "(worst case uses ~52% of context). char→token ratio (~1.45) calibrated from v2's "
        "recorded `input_tokens`.",
        "- **No context overflow.** Safety check ran over all 100 questions' (v2) retrieved "
        "page-sets at the new cap; max was Q75 above.",
        "",
    ]

    # ---- 2. Regression recovery ----
    L += [
        "## 2. Regression Recovery — Q59, Q84, Q91 (the v2 regressions)",
        "",
        "The v2 report attributed Q84 to truncation and Q59/Q91 to the confusable-`甄宝玉` "
        "distractor. The v3 data **revises that**: Q59 also turns out to be a truncation casualty "
        "(its answer lives past char 4000 in the 21K-char 贾宝玉 page) and recovers; Q84 recovers "
        "to its v1 partial-answer; only Q91 persists, and for a reason that is neither truncation "
        "nor the distractor — a genuine missing-content gap (see below).",
        "",
    ]
    for qid in REGRESSION_IDS:
        a2, a3 = v2[qid], v3[qid]
        verdict, diag = REGRESSION_VERDICTS[qid]
        L += [
            f"### Q{qid} — **{verdict}**",
            "",
            f"**Q:** {a2['question']}",
            "",
            f"_Adjudication:_ {diag}",
            "",
            f"_(strict-refusal flag: v2={refused(a2['answer'])} → v3={refused(a3['answer'])}; "
            f"pure-refusal: v2={pure_refused(a2['answer'])} → v3={pure_refused(a3['answer'])})_",
            "",
            "| | v2 | v3 |",
            "|---|---|---|",
            f"| **Answer** | {md_cell(a2['answer'])} | {md_cell(a3['answer'])} |",
            f"| **Len** | {len(a2['answer'])} | {len(a3['answer'])} |",
            f"| **Retrieved** | {', '.join('`'+p+'`' for p in a2['retrieved_page_paths'])} | "
            f"{', '.join('`'+p+'`' for p in a3['retrieved_page_paths'])} |",
            "",
        ]
    L += [
        "**Recovery summary:** 2 of 3 regressions recovered (Q59 fully, Q84 to v1's partial "
        "answer). Q91 persists for a reason outside this fix's scope (a missing-content/ingest "
        "gap, not truncation).",
        "",
    ]

    # ---- 3. Fragmentation casualties ----
    L += [
        "## 3. Original Fragmentation Casualties — Q38, Q65, Q97 (v3 status)",
        "",
        "Form-level status only (substantive answer vs refusal); correctness is the evaluator's "
        "call.",
        "",
        "| Q | tier | v1 | v2 | v3 | v3 form-status |",
        "|---|---|---|---|---|---|",
    ]
    for qid in CASUALTY_IDS:
        def st(d):
            return "refusal" if refused(d[qid]["answer"]) else "answer"
        v3status = "REFUSAL" if refused(v3[qid]["answer"]) else "SUBSTANTIVE"
        L.append(f"| Q{qid} | {v1[qid]['tier']} | {st(v1)} | {st(v2)} | {st(v3)} | {v3status} |")
    L.append("")

    # ---- 4. Refusal counts ----
    # Among the merged-page late-chapter questions, show net movement v2->v3
    moved_to_answer = [q for q in v2 if refused(v2[q]["answer"]) and not refused(v3[q]["answer"])]
    moved_to_refuse = [q for q in v2 if not refused(v2[q]["answer"]) and refused(v3[q]["answer"])]
    L += [
        "## 4. Refusal Counts Across Versions (out of 100)",
        "",
        "Two definitions: **strict** = answer contains “wiki 未提供足够信息” (this over-counts "
        "*partial* answers like Q84 that answer most of a question but flag one missing sub-part). "
        "**pure** = the phrase appears AND the answer carries no `第X回` citation (essentially no "
        "substantive content). The truth is between them; both move the same direction.",
        "",
        "| Version | Strict refusals | Pure refusals |",
        "|---|---:|---:|",
        f"| v1 (pre-merge) | {v1_ref} | {v1_pure} |",
        f"| v2 (merged, cap 4000) | {v2_ref} | {v2_pure} |",
        f"| v3 (merged, cap 24000) | {v3_ref} | {v3_pure} |",
        "",
        f"**The cap bump roughly halved refusals** (strict {v2_ref}→{v3_ref}, pure "
        f"{v2_pure}→{v3_pure}) — the clearest improvement of any fix so far. Mechanism: "
        "late-chapter content on the large merged pages (贾宝玉 21K, 贾母 13K, 王熙凤 13K, 林黛玉 "
        "11K, 薛宝钗 10K chars) is now visible to the model instead of being cut at char 4000.",
        "",
        f"Strict v2 → v3 movement: **{len(moved_to_answer)}** refusals lifted, "
        f"**{len(moved_to_refuse)}** newly introduced (Q{sorted(moved_to_refuse)}). "
        "(Single-sample; see §5.)",
        "",
    ]

    # ---- 5. Nondeterminism caveat ----
    L += [
        "## 5. Nondeterminism Caveat",
        "",
        "DeepSeek-V3 is **not deterministic at `temperature=0`**: the v2 diagnostic probe found "
        "~68% of identical-retrieval questions produced different answer *wording* on rerun, and "
        "even refusal status flips on a minority of borderline questions (~2/14 probed). "
        "Therefore:",
        "",
        "- Raw “answer text changed v2→v3” counts are **noise**, not a fix signal — ignore them.",
        "- **Refusal-status** changes are the more reliable signal, but single-sample refusal "
        "flips on borderline questions can still be nondeterministic. A clean read of this fix's "
        "effect would average ≥3 reruns per question; the counts above are single-sample.",
        "- The fix's *intended* effect is narrow and mechanical: make late-chapter content on the "
        "few large merged pages **visible** to the model (it no longer gets truncated). Whether "
        "the model then uses it is subject to the same generation noise.",
        "",
        "## Cost — ⚠️ BUDGET EXCEEDED",
        "",
        f"- Extra spend this task (v3 run): **${d_cost:.4f}** (wiki_query delta) / "
        f"${d_total:.4f} overall — embeddings free (index reused, not rebuilt).",
        f"- {d_calls} wiki_query calls, {d_in:,} input + {d_out:,} output tokens (input cost "
        "dominates).",
        f"- **Part 1 budget cap was $0.30; actual ${d_cost:.4f} → {d_cost / 0.30 * 100:.0f}% of "
        f"cap (over by ${d_cost - 0.30:.4f}).**",
        "- **Cause:** the 4000→24000 cap raised per-call input tokens on big-page questions "
        "(e.g. Q75: ~7K → 33K input tokens). At DeepSeek's $0.27/1M input, the v3 run cost "
        f"${d_cost:.2f} vs ~$0.16 for the v2 run. The cost scales with how much page text is now "
        "sent — foreseeable in hindsight from the token projection, which I checked for *overflow* "
        "but did not convert to a *dollar* estimate before running.",
        "- Per the Part 1 hard constraint (“extra spend < $0.30; if exceeded, STOP and report”), "
        "this triggers a **STOP**. The v3 run had already completed when the post-run budget check "
        "ran, so the spend is locked; **Part 2 (git force-push) was NOT started.**",
        "",
    ]

    REPORT.write_text("\n".join(L), encoding="utf-8")
    print(f"Wrote {REPORT}")
    print(f"  refusals v1={v1_ref} v2={v2_ref} v3={v3_ref}; extra_spend=${d_cost:.4f}")
    for qid in REGRESSION_IDS:
        print(f"  Q{qid}: v2_refused={refused(v2[qid]['answer'])} v3_refused={refused(v3[qid]['answer'])}")


if __name__ == "__main__":
    main()
