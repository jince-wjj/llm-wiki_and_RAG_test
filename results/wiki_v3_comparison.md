# Wiki v3 Comparison Report

v3 changes exactly one thing vs v2: the per-page truncation cap in `src/wiki_query.py::format_page_block` (**4000 → 24000 chars**). Everything else is unchanged — same merged 438-page wiki, same BGE-M3 vector index (loaded, not rebuilt), same answer model (`deepseek-chat`/DeepSeek-V3), prompt, `max_tokens=400`, `temperature=0.0`, `top-k=5`. RAG side untouched. v1/v2 answer files preserved.

## 1. The Fix

- **Old per-page cap:** 4000 chars
- **New per-page cap:** 24000 chars
- **Largest merged page:** `人物/贾宝玉.md` at **21,039 chars** — now fully included (cap 24,000 leaves ~2,961 chars headroom). Only one page (贾宝玉) exceeded the 16000 floor, so the cap was raised above it.
- **Max total prompt after change:** Q75 at 46,071 chars ≈ **31,791 tok** (median ratio) / **33,471 tok** (conservative). DeepSeek-V3 context ≈ 64K tok; 55K stop-threshold **not approached** (worst case uses ~52% of context). char→token ratio (~1.45) calibrated from v2's recorded `input_tokens`.
- **No context overflow.** Safety check ran over all 100 questions' (v2) retrieved page-sets at the new cap; max was Q75 above.

## 2. Regression Recovery — Q59, Q84, Q91 (the v2 regressions)

The v2 report attributed Q84 to truncation and Q59/Q91 to the confusable-`甄宝玉` distractor. The v3 data **revises that**: Q59 also turns out to be a truncation casualty (its answer lives past char 4000 in the 21K-char 贾宝玉 page) and recovers; Q84 recovers to its v1 partial-answer; only Q91 persists, and for a reason that is neither truncation nor the distractor — a genuine missing-content gap (see below).

### Q59 — **RECOVERED**

**Q:** 宝玉去黛玉房中时，黛玉因看见宝玉脸上的血渍，说了什么话？

_Adjudication:_ v3 returns the exact line (“你又干这些事了…”). The quote lives in 贾宝玉.md's 第19回 section, which sat *past* the old 4000-char cap (贾宝玉.md is 21K chars). So Q59 was a truncation casualty too — correcting the v2 report, which had attributed it to the 甄宝玉 distractor alone.

_(strict-refusal flag: v2=True → v3=False; pure-refusal: v2=False → v3=False)_

| | v2 | v3 |
|---|---|---|
| **Answer** | 根据 wiki 页面“人物/林黛玉.md”第19回更新记载，黛玉发现宝玉腮上血渍，知是淘胭脂，用自己的帕子替他揩拭。但页面未明确记载黛玉说了什么具体话语。因此，wiki 未提供足够信息。 | 根据 wiki 页面“人物/林黛玉.md”第19回更新记载，黛玉发现宝玉腮上血渍，知是淘胭脂，用自己的帕子替他揩拭，并说：“你又干这些事了。干也罢了，必定还要带出幌子来。” 因此，黛玉说的是：“你又干这些事了。干也罢了，必定还要带出幌子来。” |
| **Len** | 93 | 121 |
| **Retrieved** | `人物/贾宝玉.md`, `事件/贾宝玉梦甄宝玉.md`, `人物/甄宝玉.md`, `人物/林黛玉.md`, `事件/黛玉葬花.md` | `人物/贾宝玉.md`, `事件/贾宝玉梦甄宝玉.md`, `人物/甄宝玉.md`, `人物/林黛玉.md`, `事件/黛玉葬花.md` |

### Q84 — **RECOVERED (partial)**

**Q:** 薛蟠从江南带回的土仪中，宝钗如何分配？林黛玉收到后有何反应？

_Adjudication:_ The previously-truncated 第67回 line is back: v3 correctly states 宝钗 distributed the gifts with 黛玉's share doubled (（第67回）). It only notes 黛玉's *reaction* as missing — which is genuinely absent from the wiki, not a truncation effect. This is exactly v1's partial-answer behavior, so the truncation regression is reversed. (The strict refusal regex still flags it because the phrase appears for the unanswerable sub-part; it is **not** a pure refusal.)

_(strict-refusal flag: v2=True → v3=True; pure-refusal: v2=True → v3=False)_

| | v2 | v3 |
|---|---|---|
| **Answer** | 根据 wiki 页面，薛蟠从江南带回的土仪中，宝钗如何分配以及林黛玉收到后的反应，wiki 未提供足够信息。页面仅提到薛蟠带回两箱子东西，一箱绸缎绫锦洋货，一箱笔墨纸砚等物，内有虎丘泥人小像，并听从母亲和宝钗建议下帖请伙计吃酒，但未说明宝钗如何分配这些物品，也未提及林黛玉收到后的反应。 | 根据 wiki 页面记载，宝钗将薛蟠从江南带回的礼物一分分配妥当，送给各人，其中黛玉的比别人加厚一倍（第67回）。但页面未提及林黛玉收到后的具体反应，因此无法回答此部分。wiki 未提供足够信息。 |
| **Len** | 143 | 98 |
| **Retrieved** | `人物/薛蟠.md`, `事件/薛蟠外出经商.md`, `事件/薛蟠娶夏金桂.md`, `人物/薛宝钗.md`, `事件/宝钗借扇机带双敲.md` | `人物/薛蟠.md`, `事件/薛蟠外出经商.md`, `事件/薛蟠娶夏金桂.md`, `人物/薛宝钗.md`, `事件/宝钗借扇机带双敲.md` |

### Q91 — **STILL_REFUSING (expected, out of scope)**

**Q:** 第5回中，宝玉在秦可卿房中午睡，梦中与可卿（兼美）成姻；而第8回末尾交代秦可卿身世，说她是养生堂抱养的，且‘生的形容袅娜，性格风流’。这两处对秦可卿的描写是否存在矛盾？

_Adjudication:_ Not truncation: 薛宝钗/秦可卿 pages are now fully included, but the question needs 第8回 秦可卿 origin content (养生堂 abandoned-child detail) that was never ingested onto any retrieved page. v3 supplies 第5回/第10回 facts but cannot confirm the contradiction. A content-gap / ingest issue, not the page cap.

_(strict-refusal flag: v2=True → v3=True; pure-refusal: v2=False → v3=False)_

| | v2 | v3 |
|---|---|---|
| **Answer** | 根据提供的 wiki 页面，第5回描述宝玉在秦可卿房中午睡，梦中与兼美（乳名可卿）成姻，而秦可卿在现实中是贾蓉之妻，生的袅娜纤巧。第8回末尾未在页面中提及秦可卿身世为养生堂抱养，且“生的形容袅娜，性格风流”未出现在第8回更新中。页面未提供第8回关于秦可卿身世的详细信息，因此无法判断是否存在矛盾。wiki 未提供足够信息。 | 根据wiki页面信息，第5回中宝玉在秦可卿房中午睡，梦游太虚幻境，与警幻仙子之妹（乳名兼美，字可卿）成姻，而秦可卿本人是贾蓉之妻。第8回末尾未在提供的页面中提及秦可卿身世，但第5回和第10回均描述她“生的袅娜纤巧，行事温柔和平”。页面未显示第8回内容，因此无法确认是否存在矛盾。wiki未提供足够信息。 |
| **Len** | 161 | 151 |
| **Retrieved** | `人物/贾宝玉.md`, `事件/贾宝玉梦甄宝玉.md`, `人物/甄宝玉.md`, `人物/秦可卿.md`, `事件/秦可卿之死.md` | `人物/贾宝玉.md`, `事件/贾宝玉梦甄宝玉.md`, `人物/甄宝玉.md`, `人物/秦可卿.md`, `事件/秦可卿之死.md` |

**Recovery summary:** 2 of 3 regressions recovered (Q59 fully, Q84 to v1's partial answer). Q91 persists for a reason outside this fix's scope (a missing-content/ingest gap, not truncation).

## 3. Original Fragmentation Casualties — Q38, Q65, Q97 (v3 status)

Form-level status only (substantive answer vs refusal); correctness is the evaluator's call.

| Q | tier | v1 | v2 | v3 | v3 form-status |
|---|---|---|---|---|---|
| Q38 | Tier 2 | refusal | refusal | answer | SUBSTANTIVE |
| Q65 | Tier 3 | refusal | refusal | refusal | REFUSAL |
| Q97 | Tier 4 | refusal | refusal | answer | SUBSTANTIVE |

## 4. Refusal Counts Across Versions (out of 100)

Two definitions: **strict** = answer contains “wiki 未提供足够信息” (this over-counts *partial* answers like Q84 that answer most of a question but flag one missing sub-part). **pure** = the phrase appears AND the answer carries no `第X回` citation (essentially no substantive content). The truth is between them; both move the same direction.

| Version | Strict refusals | Pure refusals |
|---|---:|---:|
| v1 (pre-merge) | 35 | 19 |
| v2 (merged, cap 4000) | 34 | 18 |
| v3 (merged, cap 24000) | 17 | 11 |

**The cap bump roughly halved refusals** (strict 34→17, pure 18→11) — the clearest improvement of any fix so far. Mechanism: late-chapter content on the large merged pages (贾宝玉 21K, 贾母 13K, 王熙凤 13K, 林黛玉 11K, 薛宝钗 10K chars) is now visible to the model instead of being cut at char 4000.

Strict v2 → v3 movement: **17** refusals lifted, **0** newly introduced (Q[]). (Single-sample; see §5.)

## 5. Nondeterminism Caveat

DeepSeek-V3 is **not deterministic at `temperature=0`**: the v2 diagnostic probe found ~68% of identical-retrieval questions produced different answer *wording* on rerun, and even refusal status flips on a minority of borderline questions (~2/14 probed). Therefore:

- Raw “answer text changed v2→v3” counts are **noise**, not a fix signal — ignore them.
- **Refusal-status** changes are the more reliable signal, but single-sample refusal flips on borderline questions can still be nondeterministic. A clean read of this fix's effect would average ≥3 reruns per question; the counts above are single-sample.
- The fix's *intended* effect is narrow and mechanical: make late-chapter content on the few large merged pages **visible** to the model (it no longer gets truncated). Whether the model then uses it is subject to the same generation noise.

## Cost — ⚠️ BUDGET EXCEEDED

- Extra spend this task (v3 run): **$0.3854** (wiki_query delta) / $0.3854 overall — embeddings free (index reused, not rebuilt).
- 300 wiki_query calls, 1,385,537 input + 11,284 output tokens (input cost dominates).
- **Part 1 budget cap was $0.30; actual $0.3854 → 128% of cap (over by $0.0854).**
- **Cause:** the 4000→24000 cap raised per-call input tokens on big-page questions (e.g. Q75: ~7K → 33K input tokens). At DeepSeek's $0.27/1M input, the v3 run cost $0.39 vs ~$0.16 for the v2 run. The cost scales with how much page text is now sent — foreseeable in hindsight from the token projection, which I checked for *overflow* but did not convert to a *dollar* estimate before running.
- Per the Part 1 hard constraint (“extra spend < $0.30; if exceeded, STOP and report”), this triggers a **STOP**. The v3 run had already completed when the post-run budget check ran, so the spend is locked; **Part 2 (git force-push) was NOT started.**
