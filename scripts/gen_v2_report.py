"""Generate results/wiki_v2_comparison.md from merge log + v1/v2 answer files + usage.

Run AFTER scripts/run_wiki_v2.py has completed, from project root:
    python -m scripts.gen_v2_report

Reads:
  - /tmp/wiki_merge/merge_log.json       (per-pair merge stats)
  - /tmp/wiki_merge/usage_before_v2.json (pre-task usage snapshot)
  - results/wiki_answers.json            (v1)
  - results/wiki_answers_v2.json         (v2)
  - usage.json                           (post-task usage)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]

MERGE_LOG = Path("/tmp/wiki_merge/merge_log.json")
V1_ANSWERS = PROJ / "results/wiki_answers.json"
V2_ANSWERS = PROJ / "results/wiki_answers_v2.json"
USAGE_BEFORE = Path("/tmp/wiki_merge/usage_before_v2.json")
USAGE_NOW = PROJ / "usage.json"
REPORT_PATH = PROJ / "results/wiki_v2_comparison.md"
# Persisted nondeterminism probe outputs (committed alongside the report).
V2_PROBE = PROJ / "results/wiki_v2_diag_v2probe.json"   # frozen v2 retrieval, 3 reps
V1_PROBE = PROJ / "results/wiki_v2_diag_v1probe.json"   # reconstructed v1 retrieval, 3 reps

SANITY_IDS = [21, 4, 1, 54, 39, 38, 68, 65, 84, 87, 96, 97]
REFUSAL_PATTERN = re.compile(r"wiki\s*未提供足够信息")

# Discovered substring candidates that were NOT merged (different entities).
SKIPPED_PAIRS_INFO = [
    ("吴新登", "吴新登家的", "管家吴新登 vs 其妻（不同人物）"),
    ("宝玉", "甄宝玉", "贾宝玉 vs 甄宝玉（江南甄家之子，不同人物）"),
    ("尤氏", "尤氏母亲", "尤氏 vs 其母（不同人物）"),
    ("彩霞", "彩霞之母", "丫鬟彩霞 vs 其母（不同人物）"),
    ("旺儿", "旺儿媳妇", "来旺儿 vs 其妻（不同人物）"),
    ("春燕", "春燕姑妈", "小丫头春燕 vs 其姑妈（不同人物）"),
    ("李纨", "李纨寡婶", "李纨 vs 其寡婶（不同人物）"),
    ("林之孝", "林之孝家的", "林之孝 vs 其妻（不同人物）"),
    ("贾芸", "贾芸母亲", "贾芸 vs 其母（不同人物）"),
    ("贾蓉", "贾蓉之妻", "贾蓉 vs 其妻秦可卿（不同人物）"),
    ("赖大", "赖大家的", "赖大 vs 其妻（不同人物）"),
    ("赖大", "赖大母亲", "赖大 vs 赖嬷嬷（不同人物）"),
    ("金文翔", "金文翔媳妇", "金文翔 vs 其妻（不同人物）"),
    ("金荣", "金荣母亲胡氏", "金荣 vs 其母胡氏（不同人物）"),
    ("鲍二", "鲍二家的", "鲍二 vs 其妻（不同人物）"),
]


def normalize_for_diff(text: str) -> str:
    """Collapse all whitespace for substantive-diff comparison (ignores whitespace/layout)."""
    return re.sub(r"\s+", "", text or "").strip()


def has_refusal(answer: str) -> bool:
    return bool(REFUSAL_PATTERN.search(answer or ""))


def judge_form(v1_ans: str, v2_ans: str) -> str:
    """IMPROVED / REGRESSED / NEUTRAL / NO_CHANGE — FORM ONLY (substance/coverage, not correctness)."""
    v1_norm = normalize_for_diff(v1_ans)
    v2_norm = normalize_for_diff(v2_ans)
    if v1_norm == v2_norm:
        return "NO_CHANGE"
    v1_ref = has_refusal(v1_ans)
    v2_ref = has_refusal(v2_ans)
    if v1_ref and not v2_ref:
        return "IMPROVED"   # refusal -> substantive answer
    if not v1_ref and v2_ref:
        return "REGRESSED"  # substantive answer -> refusal
    if len(v2_norm) >= len(v1_norm) * 1.2:
        return "IMPROVED"
    if len(v1_norm) >= len(v2_norm) * 1.2:
        return "REGRESSED"
    return "NEUTRAL"


def md_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", "<br>") or "*(empty)*"


def main() -> None:
    merge_log = json.loads(MERGE_LOG.read_text(encoding="utf-8"))
    v1 = json.loads(V1_ANSWERS.read_text(encoding="utf-8"))
    v2 = json.loads(V2_ANSWERS.read_text(encoding="utf-8"))
    usage_before = json.loads(USAGE_BEFORE.read_text(encoding="utf-8"))
    usage_now = json.loads(USAGE_NOW.read_text(encoding="utf-8"))

    v1_by_id = {a["question_id"]: a for a in v1}
    v2_by_id = {a["question_id"]: a for a in v2}

    # ---- Section 1: merge summary ----
    s1 = ["## 1. Merge Summary", ""]
    s1.append(
        "| Dupe | Canonical | Dupe (B) | Canon before (B) | Canon after (B) | "
        "Ch inserted | Ch deduped | Supplements |"
    )
    s1.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for m in merge_log:
        s1.append(
            f"| `{m['dupe'][:-3]}` | `{m['canonical'][:-3]}` | {m['dupe_size_before']} | "
            f"{m['canonical_size_before']} | {m['canonical_size_after']} | "
            f"{m['chapters_inserted']} | {m['chapters_duplicated_skipped']} | "
            f"{m['chapters_appended_as_supplement']} |"
        )
    s1 += [
        "",
        f"**{len(merge_log)} pairs merged** = 3 known (黛玉/宝玉/宝钗) + "
        f"{len(merge_log) - 3} discovered via the Step-1 substring scan.",
        "",
        "Merge policy: dupe chapter-blocks were merged into the canonical page in ascending "
        "chapter order. Per-chapter content already present verbatim in the canonical was "
        "**deduped** (column *Ch deduped*); content for a chapter present in both but with "
        "*different* bullets was kept as a labelled supplement block (column *Supplements*); "
        "chapters only in the dupe were **inserted** (column *Ch inserted*). No information was "
        "deleted. Each canonical's `aliases` now includes the short name; `source_count` was "
        "summed.",
        "",
        "### Discovered but NOT merged (false positives — distinct entities)",
        "",
        "These substring matches cleared the >200-byte gate but name different people "
        "(relative/spouse/servant pages, or 贾宝玉 vs 甄宝玉). Per the conservative-merge rule "
        "they were left untouched:",
        "",
        "| Shorter | Longer | Reason |",
        "|---|---|---|",
    ]
    for short, long, reason in SKIPPED_PAIRS_INFO:
        s1.append(f"| `{short}` | `{long}` | {reason} |")
    s1.append("")

    # ---- Section 2: retrieval shift ----
    s2 = ["## 2. Retrieval Shift", ""]
    s2.append(
        "Counts of how often each entity's page(s) appeared in the top-5 retrieved set across "
        "the 100 questions. In v1 the entity was split across canonical + dupe; *v1 either* is "
        "the deduped union of the two (the true v1 reach), *v1 both* is questions that wasted two "
        "of their five slots on the same entity. v2 has a single unified page."
    )
    s2 += [
        "",
        "| Canonical | Alias | v1 canon | v1 dupe | v1 either | v1 both | v2 canon |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for m in merge_log:
        canon_stem = m["canonical"][:-3]
        dupe_stem = m["dupe"][:-3]
        cp = f"人物/{canon_stem}.md"
        dp = f"人物/{dupe_stem}.md"
        v1_c = sum(1 for a in v1 if cp in (a.get("retrieved_page_paths") or []))
        v1_d = sum(1 for a in v1 if dp in (a.get("retrieved_page_paths") or []))
        v1_e = sum(
            1 for a in v1
            if cp in (a.get("retrieved_page_paths") or []) or dp in (a.get("retrieved_page_paths") or [])
        )
        v1_b = sum(
            1 for a in v1
            if cp in (a.get("retrieved_page_paths") or []) and dp in (a.get("retrieved_page_paths") or [])
        )
        v2_c = sum(1 for a in v2 if cp in (a.get("retrieved_page_paths") or []))
        s2.append(f"| `{canon_stem}` | `{dupe_stem}` | {v1_c} | {v1_d} | {v1_e} | {v1_b} | {v2_c} |")
    total_v1_both = 0
    for m in merge_log:
        cp = f"人物/{m['canonical'][:-3]}.md"
        dp = f"人物/{m['dupe'][:-3]}.md"
        total_v1_both += sum(
            1 for a in v1
            if cp in (a.get("retrieved_page_paths") or []) and dp in (a.get("retrieved_page_paths") or [])
        )
    s2 += [
        "",
        f"In v1, **{total_v1_both} (question × entity)** slots were wasted on a duplicate page of "
        "an entity already retrieved — those slots are now freed for other pages, which is the "
        "mechanism behind the answer changes below.",
        "",
    ]

    # ---- Section 3: per-question diff (12 sanity checks) ----
    s3 = ["## 3. Per-Question Diff — 12 Sanity-Check Questions", ""]
    s3.append(
        "Verdict is **form only** — whether v2 is more substantive / covers more ground / flips a "
        "refusal. Correctness is the evaluator's call, not judged here.",
    )
    s3.append("")
    counts = {"IMPROVED": 0, "REGRESSED": 0, "NEUTRAL": 0, "NO_CHANGE": 0}
    for qid in SANITY_IDS:
        v1a = v1_by_id.get(qid)
        v2a = v2_by_id.get(qid)
        if v1a is None or v2a is None:
            s3.append(f"### Q{qid} — MISSING (v1={v1a is not None}, v2={v2a is not None})")
            s3.append("")
            continue
        verdict = judge_form(v1a["answer"], v2a["answer"])
        counts[verdict] += 1
        s3.append(f"### Q{qid} [{v1a['tier']}] — **{verdict}**")
        s3.append("")
        s3.append(f"**Q:** {v1a['question']}")
        s3.append("")
        v1_paths = ", ".join(f"`{p}`" for p in (v1a.get("retrieved_page_paths") or [])) or "(none)"
        v2_paths = ", ".join(f"`{p}`" for p in (v2a.get("retrieved_page_paths") or [])) or "(none)"
        s3 += [
            "| | v1 | v2 |",
            "|---|---|---|",
            f"| **Answer** | {md_cell(v1a['answer'])} | {md_cell(v2a['answer'])} |",
            f"| **Length** | {len(v1a['answer'])} chars | {len(v2a['answer'])} chars |",
            f"| **Retrieved** | {v1_paths} | {v2_paths} |",
            "",
        ]
    s3.append("**Sanity totals:** " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    s3.append("")

    # ---- Section 4: full-set diff stats ----
    diff_count = refusal_reversed = refusal_introduced = 0
    length_deltas = []
    reversed_ids, introduced_ids = [], []
    for qid, v1a in v1_by_id.items():
        v2a = v2_by_id.get(qid)
        if v2a is None:
            continue
        if normalize_for_diff(v1a["answer"]) != normalize_for_diff(v2a["answer"]):
            diff_count += 1
        v1r, v2r = has_refusal(v1a["answer"]), has_refusal(v2a["answer"])
        if v1r and not v2r:
            refusal_reversed += 1
            reversed_ids.append(qid)
        if not v1r and v2r:
            refusal_introduced += 1
            introduced_ids.append(qid)
        length_deltas.append(len(v2a["answer"]) - len(v1a["answer"]))
    mean_delta = sum(length_deltas) / len(length_deltas) if length_deltas else 0.0
    v1_refusals = sum(1 for a in v1 if has_refusal(a["answer"]))
    v2_refusals = sum(1 for a in v2 if has_refusal(a["answer"]))
    s4 = [
        "## 4. Full-Set Diff Stats (100 questions)",
        "",
        f"- **Substantively different (v2 ≠ v1, whitespace-normalized):** {diff_count} / 100",
        f"- **Refusals reversed** (v1 said “wiki 未提供足够信息”, v2 answered): **{refusal_reversed}**"
        + (f"  → Q{reversed_ids}" if reversed_ids else ""),
        f"- **Refusals introduced** (v1 answered, v2 refused): **{refusal_introduced}**"
        + (f"  → Q{introduced_ids}" if introduced_ids else " (target: ~0)"),
        f"- **Total refusals:** v1 = {v1_refusals}, v2 = {v2_refusals}",
        f"- **Mean answer-length change:** {mean_delta:+.1f} chars (v2 − v1)",
        "",
        "> ⚠️ The raw `diff` count (82/100) is dominated by **generation nondeterminism**, not by "
        "the merge: of the 38 questions whose retrieved page-set was *identical* between v1 and "
        "v2, 26 (68%) still produced different answer text. DeepSeek-V3 is not deterministic at "
        "`temperature=0`. Answer **text** therefore cannot be attributed to the merge; the "
        "**refusal-status** and **retrieval** metrics are far more stable (see §6).",
        "",
    ]

    # ---- Section 5: cost ----
    dt_total = usage_now["estimated_cost_usd"] - usage_before["estimated_cost_usd"]
    wb = usage_before["by_phase"]["wiki_query"]
    wn = usage_now["by_phase"]["wiki_query"]
    d_in = wn["input_tokens"] - wb["input_tokens"]
    d_out = wn["output_tokens"] - wb["output_tokens"]
    d_calls = wn["calls"] - wb["calls"]
    d_cost = wn["cost_usd"] - wb["cost_usd"]
    s5 = [
        "## 5. Cost (extra spend for this task)",
        "",
        "- **Embeddings** (BGE-M3 via SiliconFlow, free tier): 438 page vectors re-embedded on "
        "index rebuild + one query vector per question. Logged but **$0**.",
        f"- **DeepSeek wiki_query calls:** {d_calls} (entity-extraction + answer + embedding calls; "
        "includes the stop/resume index rebuild and a few retries).",
        f"- **DeepSeek tokens:** {d_in:,} input + {d_out:,} output.",
        f"- **Additional spend: ${d_cost:.4f}** (phase delta) — matches overall delta ${dt_total:.4f}.",
        f"- Pre-task total: ${usage_before['estimated_cost_usd']:.4f} → post-task total: "
        f"${usage_now['estimated_cost_usd']:.4f}.",
        f"- Budget cap for this task was $1.00 extra → **{d_cost / 1.00 * 100:.0f}% of cap used.**",
        "",
    ]

    # ---- Section 6: root-cause analysis & nondeterminism diagnostics ----
    s6 = ["## 6. Root-Cause Analysis & Nondeterminism Diagnostics", ""]
    s6 += [
        "Because answer text is noisy at `temperature=0`, the only trustworthy quality signal is "
        "whether an answer **refuses** (“wiki 未提供足够信息”). Two controlled probes were run "
        "(diagnostic only — they do not touch the official v2 results):",
        "",
        "- **v2-frozen probe** (`results/wiki_v2_diag_v2probe.json`): hold each question's v2 "
        "retrieved page-set fixed, re-call the answer model 3×.",
        "- **v1-reconstructed probe** (`results/wiki_v2_diag_v1probe.json`): rebuild each "
        "question's *pre-merge* 5-page context from the `HEAD~1` git state (recovering the deleted "
        "dupe pages), re-call 3×.",
        "",
    ]
    try:
        v2p = {r["qid"]: r for r in json.loads(V2_PROBE.read_text(encoding="utf-8"))}
        v1p = {r["qid"]: r for r in json.loads(V1_PROBE.read_text(encoding="utf-8"))}
        # Noise floor across all probed questions in the v2 probe
        flips = sum(1 for r in v2p.values() if 0 < r["rep_refusals"] < r["reps"])
        s6 += [
            f"**Refusal noise floor:** across the {len(v2p)} probed edge questions, only "
            f"**{flips}** flipped refusal status across identical-input reps — so the refusal "
            "metric is mostly stable (unlike the 68% text churn).",
            "",
            "### The 5 \"introduced\" refusals, adjudicated",
            "",
            "| Q | v1 reconstructed (refuse/3) | v2 frozen (refuse/3) | Adjudication |",
            "|---|---:|---:|---|",
        ]
        adj = {
            48: "Borderline — v1 was already fragile (2/3 refuse); merge pushed it to 3/3.",
            59: "**Genuine regression** — v1 reliably answered, v2 reliably refuses (distractor).",
            64: "**Noise** — v1 also refuses 3/3 on rerun; original v1 answer was the lucky 1/3.",
            84: "**Genuine regression** — v1 reliably answered, v2 mostly refuses (truncation).",
            91: "**Genuine regression** — v1 reliably answered, v2 reliably refuses (distractor).",
        }
        for q in [48, 59, 64, 84, 91]:
            r1 = v1p.get(q, {}).get("rep_refusals", "?")
            r2 = v2p.get(q, {}).get("rep_refusals", "?")
            s6.append(f"| Q{q} | {r1}/3 | {r2}/3 | {adj.get(q, '')} |")
        s6 += [
            "",
            "So the headline **\"5 refusals introduced\" overstates the harm**: ~**3 genuine "
            "reproducible regressions** (Q59, Q84, Q91), 1 borderline (Q48), 1 pure noise (Q64).",
            "",
        ]
    except (OSError, ValueError, KeyError) as e:
        s6.append(f"*(probe files unavailable: {e})*")
        s6.append("")

    s6 += [
        "### Two structural mechanisms behind the regressions",
        "",
        "1. **Confusable-distractor displacement (Q59, Q91, and the 宝玉 cluster).** In v1, a 宝玉 "
        "question retrieved *both* `人物/宝玉.md` and `人物/贾宝玉.md`. Removing the dupe frees a "
        "top-5 slot, which BGE-M3 vector search then fills with the *visually/semantically "
        "confusable* `人物/甄宝玉.md` — a **different character** (the Zhen-family Bao-yu). The "
        "consolidated canonical page is still retrieved, but the added distractor measurably "
        "pushes the model toward refusal.",
        "2. **Page-truncation burial (Q84).** `src/wiki_query.py::format_page_block` truncates "
        "each page to the first **4000 chars** before sending it to the model. v1's small "
        "`宝钗.md` dupe (~3000 chars) fit entirely, so its 第67回 content was visible. After "
        "merging, 第67回 sits at char ~9017 of the 10330-char `薛宝钗.md` and is **truncated "
        "away** — the consolidated page paradoxically exposes *less* of the late-chapter content "
        "than the small dupe did. This affects late-chapter questions on the three large merged "
        "pages (`贾宝玉` 21k, `林黛玉` 11k, `薛宝钗` 10k chars).",
        "",
        "Both mechanisms are properties of the **pre-existing retrieval/formatting layer**, which "
        "the brief froze (top-k=5, no prompt/param changes, 4000-char block truncation is a "
        "retrieval parameter). They were therefore **left unchanged** — this report documents "
        "them rather than fixing them.",
        "",
        "### Net assessment",
        "",
        "- **Retrieval** (clean signal): the merge ended 100% of duplicate-page double-retrieval; "
        f"{total_v1_both} wasted (question×entity) slots were reclaimed.",
        "- **Refusals** (stable signal): ~5 reproducible reversals vs ~3 reproducible new "
        "regressions → roughly **net-neutral**, not the clean win the brief anticipated.",
        "- **Answer text** (noisy signal): not interpretable due to temp=0 nondeterminism.",
        "",
        "The fix was executed exactly as specified and lost no information on disk, but it did not "
        "by itself resolve the refusal problem. Closing the gap would require addressing the two "
        "mechanisms above (e.g. excluding `甄宝玉` as a distractor / per-page chapter-aware "
        "chunking instead of a flat 4000-char head) — both **out of scope** here because they "
        "change frozen retrieval parameters. Flagged for evaluator/user decision.",
        "",
    ]

    header = [
        "# Wiki v2 Comparison Report",
        "",
        "Before/after the alias-fragmentation fix. v2 was produced by: (1) merging 10 fragmented "
        "character pairs (3 known + 7 discovered) into their canonical full-name pages, "
        "(2) dropping and rebuilding the BGE-M3 wiki vector index over the resulting 438-page "
        "corpus, and (3) re-running the wiki query phase on all 100 benchmark questions with "
        "**unchanged** prompt, answer model (`deepseek-chat` / DeepSeek-V3), `max_tokens=400`, "
        "`temperature=0.0`, and `top-k=5`.",
        "",
        "`results/wiki_answers.json` (v1) is preserved unmodified; v2 is in "
        "`results/wiki_answers_v2.json`. RAG side untouched.",
        "",
        "**TL;DR / status: `NEEDS_USER_REVIEW`.** The merge itself is correct and lossless, but it "
        "did **not** produce the expected clean reduction in refusals — it is roughly net-neutral "
        "(~5 reproducible reversals vs ~3 reproducible new regressions). The new regressions stem "
        "from two pre-existing, out-of-scope retrieval-layer limitations (a confusable `甄宝玉` "
        "distractor and a 4000-char page truncation). See §6.",
        "",
    ]

    REPORT_PATH.write_text("\n".join(header + s1 + s2 + s3 + s4 + s5 + s6), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(f"  diff={diff_count}, refusal_reversed={refusal_reversed}, "
          f"refusal_introduced={refusal_introduced}, mean_len_delta={mean_delta:+.1f}, "
          f"extra_spend=${d_cost:.4f}")
    print(f"  sanity verdicts: {counts}")


if __name__ == "__main__":
    main()
