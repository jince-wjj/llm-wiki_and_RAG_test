"""Generate the 100-question benchmark across 4 tiers.

Tier distribution (from AGENT_INSTRUCTIONS section Phase 2):
    Tier 1 (single-fact):              30
    Tier 2 (single-source synthesis):  30
    Tier 3 (cross-source synthesis):   25
    Tier 4 (conflict/contradiction):   15
                                      ---
                                      100

Sampling:
    Tier 1/2 — sample 1 chapter
    Tier 3/4 — sample 2..5 chapters that share a major character (more likely
               to produce real cross-chapter synthesis / contradictions)

Validation:
    For each generated question, send a SEPARATE call with the cited chapters
    and ask "is this answer accurate and complete based ONLY on these
    chapters? YES/NO". Drop NO. Drop confidence < 0.8.
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from . import api_client, config, utils


# Major characters used to bias multi-chapter sampling toward shared entities.
MAJOR_CHARACTERS = [
    "贾宝玉", "林黛玉", "薛宝钗", "王熙凤", "贾母", "贾政",
    "史湘云", "妙玉", "袭人", "晴雯", "紫鹃", "探春", "迎春",
    "惜春", "元春", "秦可卿", "贾蓉", "贾琏", "贾赦", "贾珍",
    "邢夫人", "王夫人", "薛姨妈", "香菱", "李纨", "尤氏",
    "贾雨村", "甄士隐", "刘姥姥", "贾环",
]


TIER_PROMPT_DESCRIPTIONS = {
    1: (
        "单一事实题 (Tier 1)：答案必须能在单一章节中的单一句子或紧邻的几句中"
        "直接找到。例如：某人物的某次具体动作、某具体地点的描述、某物品名称、"
        "某具体诗句的作者。问题要求精确事实,不需要综合或推理。"
    ),
    2: (
        "单章节综合题 (Tier 2)：答案需要综合理解单一章节内多处分散的信息,"
        "但所有信息都来自这一章节。例如:某场景下多个人物的反应汇总、某事件的"
        "前因后果(均在本回)、某段对话的言外之意。"
    ),
    3: (
        "跨章节综合题 (Tier 3)：答案必须综合 2 个或更多章节中的信息。例如:"
        "某人物在多回中的性格演变、某事件的远因和近因横跨数回、不同章节中关于"
        "同一人物的描写如何拼合出完整形象。每道题必须明确依赖至少 2 个章节,"
        "并且仅看其中一回无法得到完整答案。"
    ),
    4: (
        "矛盾/对比题 (Tier 4)：答案需要识别多个章节中存在的不一致、张力或对比。"
        "例如：同一人物在不同章节中的不同表现/形象差异、不同人物对同一事件的"
        "相反评价、前后章节中表面信息与隐含线索的冲突。每道题必须明确指出"
        "构成对比/矛盾的章节及其细节。"
    ),
}


def build_chapter_index() -> tuple[dict[int, str], dict[str, list[int]]]:
    """Return (chapter_id -> body text, character_name -> [chapter_ids])."""
    chapters: dict[int, str] = {}
    for ch in range(1, 81):
        with open(config.RAW_CHAPTERS_DIR / f"{ch:03d}.txt", encoding="utf-8") as f:
            chapters[ch] = f.read()
    char_to_chs: dict[str, list[int]] = defaultdict(list)
    for ch_id, body in chapters.items():
        for name in MAJOR_CHARACTERS:
            if name in body:
                char_to_chs[name].append(ch_id)
    return chapters, char_to_chs


def sample_chapters_tier1_2(rng: random.Random, chapters: dict[int, str]) -> list[int]:
    """One chapter for Tier 1/2."""
    return [rng.choice(list(chapters.keys()))]


def sample_chapters_tier3_4(
    rng: random.Random,
    char_to_chs: dict[str, list[int]],
    *,
    min_n: int = 2,
    max_n: int = 5,
) -> list[int]:
    """Pick a major character with >= min_n chapter appearances, then
    sample 2-5 chapters where they appear."""
    candidates = [c for c, chs in char_to_chs.items() if len(chs) >= min_n]
    if not candidates:
        # extreme fallback (shouldn't happen with real text)
        return rng.sample(range(1, 81), min_n)
    name = rng.choice(candidates)
    pool = char_to_chs[name]
    k = rng.randint(min_n, min(max_n, len(pool)))
    return sorted(rng.sample(pool, k))


def format_chapter_block(ch_id: int, body: str, max_chars: int = 8000) -> str:
    """Format chapter text for the prompt. Truncate if very long."""
    head = f"=== 第{ch_id}回 ===\n"
    if len(body) > max_chars:
        body = body[:max_chars] + "\n[... 章节较长,已截断 ...]"
    return head + body


GENERATE_BATCH_PROMPT = """你是一名严谨的红楼梦研究者。任务是基于提供的章节内容,生成 {N} 道高质量的中文问答题。

题目类型: {TIER_DESCRIPTION}

严格要求:
1. 每道题的答案必须**完全**能从提供的章节内容中得到,不允许引入外部知识(包括续作、其他抄本、现代解读)。
2. 答案不超过200字。
3. 问题表述清晰、具体、无歧义。
4. 必须能找到 ground truth 在原文中的精确依据(指出是哪一回的哪一段)。
5. 多道题之间不要重复或高度相似。
6. 输出严格的 JSON 格式,无任何额外文字。

提供的章节内容:
{CHAPTERS}

输出格式(严格 JSON, 不要使用 markdown 代码块):
{{
  "questions": [
    {{
      "question": "...",
      "ground_truth": "...",
      "source_chapter_ids": [1, 3, 5],
      "source_evidence": "原文片段或概述",
      "tier": "{TIER_NAME}",
      "confidence": 0.85
    }}
  ]
}}
"""


VALIDATE_PROMPT = """你是红楼梦原文核对者。请仅根据下方提供的章节原文,核对一道问答题的答案是否准确且完整。

章节内容:
{CHAPTERS}

待核对的题目:
问题: {QUESTION}
答案: {GROUND_TRUTH}

判定规则:
- 若答案的所有要点都能在所提供章节中找到对应原文依据,且没有引入未在原文中出现的信息,回答 YES。
- 若答案部分内容无法在原文中找到对应依据,或与原文存在事实出入,回答 NO。
- 仅回答 YES 或 NO,后跟一句不超过30字的简短理由。

判定:"""


def generate_batch(
    *,
    tier: int,
    batch_size: int,
    chapter_ids: list[int],
    chapters: dict[int, str],
    rng: random.Random,
) -> tuple[list[dict], dict]:
    """Generate a batch of `batch_size` questions for `tier`. Returns (questions, debug)."""
    tier_name = f"Tier {tier}"
    tier_desc = TIER_PROMPT_DESCRIPTIONS[tier]
    chapter_block = "\n\n".join(format_chapter_block(c, chapters[c]) for c in chapter_ids)
    prompt = GENERATE_BATCH_PROMPT.format(
        N=batch_size,
        TIER_DESCRIPTION=tier_desc,
        TIER_NAME=tier_name,
        CHAPTERS=chapter_block,
    )

    parsed, result = api_client.chat_complete_json(
        messages=[
            {
                "role": "system",
                "content": "你是严谨的中国古典文学研究者,擅长红楼梦原文细读。",
            },
            {"role": "user", "content": prompt},
        ],
        phase="benchmark_gen",
        temperature=0.0,
        max_tokens=4000,
    )

    raw_questions = parsed.get("questions") or []
    cleaned = []
    for q in raw_questions:
        if not isinstance(q, dict):
            continue
        cleaned.append(
            {
                "question": (q.get("question") or "").strip(),
                "ground_truth": (q.get("ground_truth") or "").strip(),
                "source_chapter_ids": q.get("source_chapter_ids") or chapter_ids,
                "source_evidence": (q.get("source_evidence") or "").strip(),
                "tier": tier_name,
                "confidence": float(q.get("confidence") or 0.0),
            }
        )
    return cleaned, {
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "latency_ms": result["latency_ms"],
        "chapter_ids": chapter_ids,
    }


def validate_question(
    *,
    question: dict,
    chapters: dict[int, str],
) -> tuple[bool, str]:
    """Self-validation: ask the model whether the answer is supported. Return (ok, reason)."""
    ch_ids = question["source_chapter_ids"]
    ch_block = "\n\n".join(format_chapter_block(c, chapters[c]) for c in ch_ids if c in chapters)
    prompt = VALIDATE_PROMPT.format(
        CHAPTERS=ch_block,
        QUESTION=question["question"],
        GROUND_TRUTH=question["ground_truth"],
    )
    res = api_client.chat_complete(
        messages=[
            {
                "role": "system",
                "content": "你是严谨的红楼梦原文核对者。",
            },
            {"role": "user", "content": prompt},
        ],
        phase="benchmark_gen",
        temperature=0.0,
        max_tokens=64,
    )
    text = res["content"].strip()
    head = text[:5].upper().lstrip().lstrip("：:").lstrip()
    ok = head.startswith("YES")
    return ok, text


TIER_TARGET = {1: 30, 2: 30, 3: 25, 4: 15}
TIER_MIN_CONFIDENCE = 0.8
BATCH_SIZE = 5
# Cap chosen to bound runtime while leaving slack for T3/T4 which face
# stricter self-validation. T1/T2 converge in <10 attempts in practice;
# T3/T4 may need 20-50 due to multi-chapter synthesis errors.
MAX_ATTEMPTS_PER_TIER = 60


def run() -> None:
    if not utils.checkpoint_exists("phase1_done"):
        print("Phase 1 not complete — refusing to run Phase 2.", file=sys.stderr)
        sys.exit(2)

    print("Phase 2: benchmark generation", flush=True)
    utils.append_progress("Phase 2 started: benchmark generation")

    rng = random.Random(20260527)
    chapters, char_to_chs = build_chapter_index()
    print(
        f"Loaded {len(chapters)} chapters; "
        f"{len(char_to_chs)} major characters indexed.",
        flush=True,
    )

    # Resume support: load partial state if it exists
    partial_path = config.BENCHMARK_DIR / "_partial.json"
    if partial_path.exists():
        state = utils.read_json(partial_path)
        accepted: dict[int, list[dict]] = {int(k): v for k, v in state["accepted"].items()}
        gen_log: list[str] = state["gen_log"]
        print(
            f"Resuming. Accepted so far: "
            + ", ".join(f"T{t}={len(qs)}" for t, qs in accepted.items()),
            flush=True,
        )
    else:
        accepted = {1: [], 2: [], 3: [], 4: []}
        gen_log = []

    for tier in (1, 2, 3, 4):
        attempts = 0
        target = TIER_TARGET[tier]
        while len(accepted[tier]) < target and attempts < MAX_ATTEMPTS_PER_TIER:
            attempts += 1
            need = target - len(accepted[tier])
            batch_n = min(BATCH_SIZE, need)

            # Sample chapters
            if tier in (1, 2):
                ch_ids = sample_chapters_tier1_2(rng, chapters)
            else:
                ch_ids = sample_chapters_tier3_4(rng, char_to_chs)

            try:
                generated, debug = generate_batch(
                    tier=tier,
                    batch_size=batch_n,
                    chapter_ids=ch_ids,
                    chapters=chapters,
                    rng=rng,
                )
            except Exception as e:
                gen_log.append(
                    f"[T{tier} attempt {attempts} ch={ch_ids}] generation error: {e!r}"
                )
                print(f"  T{tier} attempt {attempts}: generation error {e!r}", flush=True)
                time.sleep(2)
                continue

            kept = 0
            dropped = 0
            for q in generated:
                if len(accepted[tier]) >= target:
                    break
                if not q["question"] or not q["ground_truth"]:
                    dropped += 1
                    continue
                if q["confidence"] < TIER_MIN_CONFIDENCE:
                    dropped += 1
                    gen_log.append(
                        f"[T{tier}] drop (confidence={q['confidence']:.2f}<{TIER_MIN_CONFIDENCE}): "
                        + q["question"][:50]
                    )
                    continue
                # Self-validation
                ok, reason = validate_question(question=q, chapters=chapters)
                if not ok:
                    dropped += 1
                    gen_log.append(
                        f"[T{tier}] drop (self-validate NO): {q['question'][:50]} | reason={reason[:50]}"
                    )
                    continue
                # De-duplication against already-accepted of this tier
                if any(
                    a["question"] == q["question"] for a in accepted[tier]
                ):
                    dropped += 1
                    continue
                accepted[tier].append(q)
                kept += 1
                gen_log.append(
                    f"[T{tier}] keep ({len(accepted[tier])}/{target}): "
                    + q["question"][:60]
                )

            print(
                f"  T{tier} attempt {attempts}: ch={ch_ids} generated={len(generated)} "
                f"kept={kept} dropped={dropped} total={len(accepted[tier])}/{target}",
                flush=True,
            )

            # Persist partial state every batch
            utils.write_json(
                partial_path,
                {
                    "accepted": {str(k): v for k, v in accepted.items()},
                    "gen_log": gen_log,
                },
            )

        if len(accepted[tier]) < target:
            msg = (
                f"Tier {tier}: only generated {len(accepted[tier])}/{target} after "
                f"{attempts} attempts. Stopping."
            )
            utils.append_blocker("Benchmark generation incomplete", msg)
            print(msg, file=sys.stderr)
            sys.exit(2)

    # Flatten + assign IDs in tier order
    questions_out = []
    ground_truth_out = []
    qid = 1
    for tier in (1, 2, 3, 4):
        for q in accepted[tier]:
            questions_out.append(
                {
                    "id": qid,
                    "question": q["question"],
                    "tier": q["tier"],
                    "source_chapter_ids": q["source_chapter_ids"],
                }
            )
            ground_truth_out.append(
                {
                    "id": qid,
                    "question": q["question"],
                    "ground_truth": q["ground_truth"],
                    "tier": q["tier"],
                    "source_chapter_ids": q["source_chapter_ids"],
                    "source_evidence": q["source_evidence"],
                    "confidence": q["confidence"],
                }
            )
            qid += 1

    utils.write_json(config.BENCHMARK_QUESTIONS, questions_out)
    utils.write_json(config.BENCHMARK_GROUND_TRUTH, ground_truth_out)

    log_md = "# Benchmark Generation Log\n\n"
    log_md += f"Generated at {utils.now_iso()}\n\n"
    log_md += "## Tier distribution\n\n"
    for tier in (1, 2, 3, 4):
        log_md += f"- Tier {tier}: {len(accepted[tier])} questions\n"
    log_md += "\n## Generation events (chronological)\n\n"
    log_md += "\n".join(f"- {line}" for line in gen_log)
    with open(config.BENCHMARK_GEN_LOG, "w", encoding="utf-8") as f:
        f.write(log_md)

    # Clean up partial
    if partial_path.exists():
        partial_path.unlink()

    utils.write_checkpoint(
        "phase2_done",
        {
            "total_questions": len(questions_out),
            "by_tier": {str(t): len(accepted[t]) for t in (1, 2, 3, 4)},
        },
    )
    utils.add_phase_complete("phase2")
    utils.append_progress(
        f"Phase 2 complete: {len(questions_out)} questions across 4 tiers"
    )
    print(
        f"Phase 2 complete: wrote {len(questions_out)} questions to {config.BENCHMARK_QUESTIONS}",
        flush=True,
    )


if __name__ == "__main__":
    run()
