"""Compile results/stats.json from the two answer files.

Section 5.4 requires aggregate stats (tokens, latency, average answer length)
per system. We also include per-tier breakdowns to make the comparison easier
for Agent 2.
"""

from __future__ import annotations

import statistics
import sys
from collections import defaultdict
from pathlib import Path

from . import config, utils


def aggregate(answers: list[dict]) -> dict:
    out = {
        "n_entries": len(answers),
        "non_empty_answers": sum(1 for a in answers if a.get("answer")),
        "total_input_tokens": sum(int(a.get("input_tokens") or 0) for a in answers),
        "total_output_tokens": sum(int(a.get("output_tokens") or 0) for a in answers),
        "total_latency_ms": sum(int(a.get("latency_ms") or 0) for a in answers),
    }
    if out["n_entries"]:
        out["avg_latency_ms"] = round(out["total_latency_ms"] / out["n_entries"], 1)
    else:
        out["avg_latency_ms"] = 0.0

    ans_lens = [len(a.get("answer") or "") for a in answers if a.get("answer")]
    if ans_lens:
        out["avg_answer_chars"] = round(statistics.mean(ans_lens), 1)
        out["median_answer_chars"] = statistics.median(ans_lens)
    else:
        out["avg_answer_chars"] = 0
        out["median_answer_chars"] = 0

    # Per-tier breakdown
    by_tier: dict[str, list[dict]] = defaultdict(list)
    for a in answers:
        by_tier[a.get("tier") or "?"].append(a)
    per_tier: dict[str, dict] = {}
    for tier, group in sorted(by_tier.items()):
        per_tier[tier] = {
            "n": len(group),
            "input_tokens": sum(int(a.get("input_tokens") or 0) for a in group),
            "output_tokens": sum(int(a.get("output_tokens") or 0) for a in group),
            "avg_latency_ms": round(
                sum(int(a.get("latency_ms") or 0) for a in group) / max(1, len(group)),
                1,
            ),
            "avg_answer_chars": round(
                statistics.mean([len(a.get("answer") or "") for a in group])
                if group
                else 0,
                1,
            ),
        }
    out["by_tier"] = per_tier
    return out


def run() -> None:
    if not config.WIKI_ANSWERS_JSON.exists() or not config.RAG_ANSWERS_JSON.exists():
        print(
            "Both answer files must exist before compiling stats.",
            file=sys.stderr,
        )
        sys.exit(2)

    wiki = utils.read_json(config.WIKI_ANSWERS_JSON)
    rag = utils.read_json(config.RAG_ANSWERS_JSON)

    stats = {
        "compiled_at": utils.now_iso(),
        "model": config.MODEL_ANSWER,
        "wiki_system": aggregate(wiki),
        "rag_baseline": aggregate(rag),
    }

    # Page counts for the wiki (from checkpoints/phase3_done.json if present)
    p3 = config.CHECKPOINTS_DIR / "phase3_done.json"
    if p3.exists():
        d = utils.read_json(p3)
        stats["wiki_pages"] = {
            "total": d.get("total_pages"),
            "by_type": d.get("by_type"),
        }
    # Chunk counts for RAG
    p4 = config.CHECKPOINTS_DIR / "phase4_done.json"
    if p4.exists():
        d = utils.read_json(p4)
        stats["rag_chunks"] = {
            "n_chunks": d.get("n_chunks"),
            "chunk_size": d.get("chunk_size"),
            "overlap": d.get("overlap"),
        }

    utils.write_json(config.STATS_JSON, stats)
    print(f"Wrote {config.STATS_JSON}")
    print(
        f"  Wiki: {stats['wiki_system']['n_entries']} answers, "
        f"avg {stats['wiki_system']['avg_answer_chars']:.0f}c, "
        f"{stats['wiki_system']['avg_latency_ms']:.0f}ms"
    )
    print(
        f"  RAG : {stats['rag_baseline']['n_entries']} answers, "
        f"avg {stats['rag_baseline']['avg_answer_chars']:.0f}c, "
        f"{stats['rag_baseline']['avg_latency_ms']:.0f}ms"
    )


if __name__ == "__main__":
    run()
