# Agent 2 Instructions: Evaluation of LLM-Wiki vs RAG Experiment

> **READ THIS DOCUMENT IN FULL BEFORE TAKING ANY ACTION.**
> **You are Agent 2 (Evaluator). Agent 1 has already built the system and generated answer files. Your job is to score those answers objectively and produce the final report.**

---

## 0. Identity, Role, and Hard Constraints

You are an autonomous evaluation agent. You evaluate two systems' answers (LLM-Wiki and vanilla RAG) on a 100-question benchmark over 《红楼梦》 前80回.

### Hard Constraints

1. **You MUST use a model different from `deepseek-chat`.** Agent 1 used DeepSeek for both answer generation and benchmark generation. You evaluate. Recommended judge model: the model running this Claude Code session itself (Claude Opus 4.7). If unavailable, use GPT-5 or Gemini 2.5 Pro via API.
2. **You MUST NOT modify any file** in `raw/`, `wiki/`, `rag_baseline/`, `benchmark/`, `results/`. Read-only access.
3. **You MUST score blind to system identity.** Implementation: when calling the judge, present `answer_A` and `answer_B` in randomized order. Record the mapping. Aggregate after scoring.
4. **You MUST NOT score using the same evaluator twice for cross-check.** Use one primary judge for all 100 questions × 2 systems = 200 scorings. Optionally use a secondary judge on a 20-question sample for reliability check.
5. **You MUST NOT speculate beyond data.** If a finding isn't supported by the scores, do not include it in the report. Speculation belongs in a clearly marked "Hypotheses for Follow-up" section, not in main findings.
6. **All scoring decisions must be reproducible.** Save the judge prompt template, all judge calls, all scores. Reading your output files, a third party must be able to reconstruct exactly what happened.
7. **Budget cap: $10 USD** for evaluation. Track in `evaluation/usage.json`.
8. **Git is enabled. You MUST commit at every evaluation phase boundary.** Same protocol as Agent 1: never push, never reset, never rebase, never amend, never branch. See Section 5.5 for details.

---

## 1. Inputs You Have Access To

Verify these exist before starting. If any is missing, STOP and write to `evaluation/BLOCKERS.md`.

| Path | Purpose |
|---|---|
| `benchmark/questions.json` | 100 questions with tier labels |
| `benchmark/ground_truth.json` | Reference answers and source chapter pointers |
| `results/wiki_answers.json` | LLM-Wiki's answers |
| `results/rag_answers.json` | RAG baseline's answers |
| `results/stats.json` | Latency and token usage stats |
| `MANIFEST.json` | Experiment metadata |
| `wiki/` | LLM-Wiki contents (for sanity-checking, NOT for scoring) |
| `rag_baseline/chunks.jsonl` | RAG chunks (for sanity-checking, NOT for scoring) |

---

## 2. Output Files You Must Produce

Everything goes under `evaluation/`. Create the directory.

| Path | Purpose |
|---|---|
| `evaluation/scores.json` | Per-question scores for both systems |
| `evaluation/judge_calls.jsonl` | Every judge API call, with prompt + response |
| `evaluation/usage.json` | API cost tracking |
| `evaluation/reliability_check.json` | Inter-judge agreement on 20-question sample (optional but recommended) |
| `evaluation/final_report.md` | Human-readable comparison report |
| `evaluation/PROGRESS.md` | Evaluation progress log |
| `evaluation/BLOCKERS.md` | Issues, if any |

---

## 3. Scoring Rubric

Use this rubric for every answer. Apply identically to both systems.

### 3.1 Three Dimensions

Each answer is scored on three dimensions, each 0–2 points:

**A. Factual Accuracy (0–2)**
- 2: All factual claims in the answer are supported by ground truth or source chapters
- 1: Mostly accurate, minor errors or omissions
- 0: Significant factual errors, fabrication, or contradiction with ground truth

**B. Completeness (0–2)**
- 2: Answer covers all key information points present in ground truth
- 1: Covers some key points but misses others
- 0: Misses most key points, or is too vague to assess

**C. Synthesis Quality (0–2)** — only for Tier 2, 3, 4 (Tier 1 gets 2 by default)
- 2: Demonstrates genuine integration of multiple information sources, identifies connections or contradictions where appropriate
- 1: Shows some integration but feels assembled rather than synthesized
- 0: Lists facts without integration, or fails to recognize required cross-source structure

**Total per question: 0–6 points.**

### 3.2 Tier-Specific Bonus Criterion

For **Tier 4 (Conflict / contradiction) questions only**, add a binary criterion:

**D. Contradiction Recognition (0 or 2)**
- 2: Answer explicitly acknowledges the inconsistency, multiple portrayals, or thematic tension that the question targets
- 0: Answer presents one version as the truth without acknowledging conflict

Tier 4 total: 0–8 points.

### 3.3 Judge Prompt Template

Use this prompt verbatim. Substitute `{...}` placeholders. Send to the judge model with `temperature=0.0`.

```
你是红楼梦研究领域的资深评审专家。任务是按照统一标准对两个 AI 系统的回答打分。

# 问题
{QUESTION}

# 标准答案 (Ground Truth)
{GROUND_TRUTH_ANSWER}

# 原文依据 (来源章节: {SOURCE_CHAPTER_IDS})
{SOURCE_EVIDENCE}

# 题目类型
{TIER} — {TIER_DESCRIPTION}

# 待评分回答 A
{ANSWER_A}

# 待评分回答 B
{ANSWER_B}

# 评分维度

1. **事实准确性 (0-2)**: 回答中的事实陈述是否被标准答案/原文支持
   - 2 = 全部准确
   - 1 = 基本准确,有小错或遗漏
   - 0 = 有显著错误、虚构、或与原文矛盾

2. **完整性 (0-2)**: 是否覆盖标准答案中的关键信息点
   - 2 = 全部关键点覆盖
   - 1 = 部分覆盖
   - 0 = 大部分关键点缺失

3. **综合质量 (0-2)**: 信息整合的深度(Tier 1 默认给 2 分,无需评估)
   - 2 = 真正整合多源信息,适当指出关联或矛盾
   - 1 = 有整合但偏向罗列
   - 0 = 纯罗列、未整合、或未识别所需的跨源结构

{TIER_4_ADDITIONAL_CRITERION}

# 评分原则

- **严格匹配标准答案,不要凭红楼梦的整体常识打分**。如果回答包含未在原文/标准答案中的内容,即使你认为是对的,也不能加分;如果与原文矛盾,扣分。
- **不要因风格、长度、用词差异打分**。只看内容。
- **不要因"看起来更详细"加分**。完整性看的是关键信息点覆盖,不是字数。
- **如果回答说"原文未提供足够信息"或"wiki 未提供足够信息",根据情况打分**:如果原文确实不足,这是诚实回答,给 1-2 分;如果原文充分但系统拒答,给 0 分。

# 输出格式 (严格 JSON)
{
  "answer_a": {
    "accuracy": 0-2,
    "completeness": 0-2,
    "synthesis": 0-2,
    {OPTIONAL_TIER_4_FIELD}
    "rationale": "简短打分理由(50字以内)"
  },
  "answer_b": {
    "accuracy": 0-2,
    "completeness": 0-2,
    "synthesis": 0-2,
    {OPTIONAL_TIER_4_FIELD}
    "rationale": "简短打分理由(50字以内)"
  }
}
```

---

## 4. Execution Phases

### Phase E0: Bootstrap

1. Verify all input files in Section 1 exist.
2. Create `evaluation/` directory.
3. Initialize `evaluation/PROGRESS.md` and `evaluation/usage.json`.
4. Decide judge model. Default: use the Claude Code model you're currently running on (preferably Opus 4.7 thinking mode). Record in `evaluation/MANIFEST.json`.
5. Read 5 random questions, 5 random wiki answers, 5 random RAG answers to sanity-check inputs. Log observations.
6. **Verify git is initialized** (`git status`). The repo already has commits from Agent 1. You will continue committing on the same default branch.
7. **First evaluation commit**: `git add -A && git commit -m "eval-phase0: evaluator bootstrap, sanity check complete"`.

### Phase E1: Blind Scoring

For each of the 100 questions:

1. Load question, ground truth, and both system answers.
2. **Randomize**: with 50% probability, present LLM-Wiki answer as A and RAG as B; else flip. Record the mapping in `judge_calls.jsonl`.
3. Construct judge prompt using the template in Section 3.3.
4. Send to judge with `temperature=0.0`.
5. Parse JSON response. If parsing fails, retry up to 2 times. If still fails, log to BLOCKERS.md and continue (do NOT skip silently).
6. De-randomize: map A/B back to wiki/rag.
7. Save to `evaluation/scores.json` as it grows. Schema:
   ```json
   {
     "question_id": "...",
     "tier": "...",
     "scores": {
       "wiki": {"accuracy": 0, "completeness": 0, "synthesis": 0, "contradiction": 0 or null, "total": 0, "rationale": "..."},
       "rag":  {"accuracy": 0, "completeness": 0, "synthesis": 0, "contradiction": 0 or null, "total": 0, "rationale": "..."}
     },
     "blinding": {"a_was": "wiki" or "rag"}
   }
   ```
8. Append full judge call (prompt + response) to `judge_calls.jsonl`.
9. Update `evaluation/usage.json` after every call.
10. Print progress every 10 questions.
11. **Git sub-commit every 25 questions**: after questions 25, 50, 75, 100, run `git add -A && git commit -m "eval-phase1: scored questions NN-MM"`.

**Exit**: 100 scored. If any question failed scoring after retries, list in BLOCKERS.md. Then `git add -A && git commit -m "eval-phase1: blind scoring complete (100 questions × 2 systems)"`.

### Phase E2: Reliability Check (Recommended, ~$2)

Run a secondary judge over 20 randomly-sampled questions (stratified across tiers: 6 from Tier 1, 6 from Tier 2, 5 from Tier 3, 3 from Tier 4).

- Secondary judge: use a different model from primary (e.g., if primary was Opus 4.7, use GPT-5 or Gemini 2.5 Pro)
- Compute agreement: for each dimension, % of questions where the two judges differ by ≤1 point
- Save to `evaluation/reliability_check.json`
- If agreement is <70% on any dimension, flag in final report (judge unreliable, results should be treated cautiously)
- Then `git add -A && git commit -m "eval-phase2: inter-judge reliability check on 20-question sample"`.

### Phase E3: Aggregate Analysis

Compute these statistics:

**Per-system, overall**:
- Mean total score
- Median total score
- Standard deviation
- Win rate (% of questions where this system scored strictly higher than the other)
- Tie rate

**Per-system, per-tier**:
- Mean total score by tier
- Win rate by tier

**Per-dimension**:
- Mean accuracy, completeness, synthesis for each system

**Tier 4 special analysis**:
- How many Tier 4 questions did each system get the "contradiction recognition" point?

**Cost / efficiency**:
- Pull from `results/stats.json`: total tokens used per system, average latency
- Compute "score per 1000 tokens" as efficiency metric

Save all aggregates to `evaluation/aggregates.json`. Then `git add -A && git commit -m "eval-phase3: aggregate statistics computed"`.

### Phase E4: Final Report

Write `evaluation/final_report.md`. Required structure:

```markdown
# LLM-Wiki vs Vanilla RAG: Experimental Results on 红楼梦 前80回

## TL;DR
[3-5 sentences. State winner per tier and overall. Quantitative. No hype.]

## Experimental Setup
- Data: 红楼梦 前80回 (X chapters, Y characters)
- LLM-Wiki: built via DeepSeek-V3 with schema in CLAUDE.md, resulting in Z pages
- RAG Baseline: chunk size 500 with 100 overlap, BGE-M3 embedding, top-5 retrieval, DeepSeek-V3 generation
- Benchmark: 100 questions across 4 tiers, generated by DeepSeek-V3 with self-validation
- Judge: [model name], blind scoring on 6-point rubric (8 for Tier 4)

## Aggregate Results

[Table: mean total score by system, with std dev]

[Table: mean score by tier, by system]

[Win/loss/tie counts]

## Per-Tier Analysis

### Tier 1 (Single Fact, n=30)
[Mean scores, key observations]

### Tier 2 (Single-Source Synthesis, n=30)
[Same]

### Tier 3 (Cross-Source Synthesis, n=25)
[Same]

### Tier 4 (Conflict Recognition, n=15)
[Same, plus contradiction-recognition rates]

## Per-Dimension Breakdown

[Accuracy, completeness, synthesis scores compared]

## Cost and Efficiency

[Tokens per system. Latency per system. Score per 1000 tokens.]

## Reliability Check

[If run: % agreement between primary and secondary judge on 20-question sample]

## Notable Observations

[3-7 bullets of patterns visible in the data. Examples:
- "On Tier 3 questions involving 3+ chapters, LLM-Wiki outperformed RAG by X points on average."
- "RAG outperformed LLM-Wiki on Tier 1 by Y points; inspection suggests wiki summarization lost some fine-grained details."
- "Both systems failed on questions requiring identification of foreshadowing across chapters."

Stick to what the data shows.]

## Hypotheses for Follow-up

[Clearly marked: speculation, not conclusion. Examples:
- "Wiki's Tier 4 advantage may depend on the explicit `## 矛盾记录` section in the schema."
- "RAG might catch up on Tier 3 with better retrieval (BM25 + rerank)."]

## Limitations of This Experiment

[Be honest. Examples:
- N=100 is small; confidence intervals are wide
- Benchmark was generated by the same model family that answered (DeepSeek)
- Single judge (or two judges) is not gold standard
- Single domain (classical literature) — results may not transfer to enterprise knowledge]

## Files in This Evaluation
[Brief inventory.]
```

**After writing the final report**: `git add -A && git commit -m "eval-phase4: final comparison report"`. This is the last commit you should make. Print to chat: "Evaluation complete. See `evaluation/final_report.md`. Last commit: eval-phase4."

---

## 5. Error Handling

- **Judge returns invalid JSON**: retry with strict instruction. After 2 retries, log and skip the question (note in BLOCKERS).
- **Judge refuses or gives non-answer**: try once more with rephrased prompt. If persists, log and skip.
- **Score appears extreme** (one system scores 0, other 6 on every question of a tier): pause, spot-check 3 such questions manually, log observations. Do not "correct" scores — just note in BLOCKERS that human review is recommended before publishing.
- **Budget exceeded**: stop immediately, write current progress to BLOCKERS, await user.

### 5.5 Git Commit Protocol

The repo was initialized by the user and Agent 1 has committed phases 0–6. You continue committing on the same default branch. Final report should land as the last commit (`eval-phase4`).

**You DO**:
- Commit at every Phase E boundary (E0, E1 done, E2 done, E3 done, E4 done).
- Sub-commit every 25 scored questions in Phase E1.
- Use commit messages prefixed `eval-phase{N}:`.
- Run `git add -A` then verify `.env` is not staged (`git diff --cached --name-only | grep -F .env` must be empty) before commit.

**You do NOT**:
- Never `git push`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout -b`, force-push, or any history-rewriting operation.
- Never modify commits Agent 1 made.
- Never stage `.env`.
- Never modify `.gitignore` (Agent 1 set it up correctly).

If commit fails for any reason other than "nothing to commit", STOP and write to BLOCKERS.md.

---

## 6. Things You Must NOT Do

1. **Do NOT modify input files** (`results/`, `benchmark/`, `wiki/`, `rag_baseline/`, `raw/`).
2. **Do NOT use DeepSeek as the judge** — same family as answer generator. Bias.
3. **Do NOT reveal system identity to the judge** in the prompt. Use "回答 A / 回答 B".
4. **Do NOT skip the reliability check** unless budget forces it (note in BLOCKERS).
5. **Do NOT write "LLM-Wiki is better than RAG" or vice versa as a categorical claim**. The result is what the data shows on this specific benchmark in this specific setup. Be precise.
6. **Do NOT generalize beyond data**. "On these 100 questions" is fine. "In general" is not.
7. **Do NOT recommend production decisions in the final report.** That's the user's job, not yours.
8. **Do NOT `git push`, `git reset --hard`, `git rebase`, `git commit --amend`, modify Agent 1's commits, or any history-rewriting operation.** See Section 5.5.
9. **Do NOT stage `.env`** under any circumstance.
10. **Do NOT modify `.gitignore`** — Agent 1 set it up.

---

## 7. Quick Reference

```
Phase E0 (Bootstrap + sanity check)
    ↓
Phase E1 (Blind scoring 100 questions × 2 systems)   ← ~30 minutes
    ↓
Phase E2 (Reliability check on 20 questions)         ← optional, ~10 minutes
    ↓
Phase E3 (Aggregate statistics)
    ↓
Phase E4 (Final report)
```

Estimated runtime: 1-2 hours. Estimated cost: $3-8.

---

## 8. Final Reminder

Read this document fully before starting. Your job is to be a **calibrated, skeptical, blind evaluator**. Not a cheerleader for either system. Not a publication-style writer. A measurement instrument.

If the data shows LLM-Wiki winning across the board, say so with the numbers. If it shows RAG winning on Tier 1 and LLM-Wiki winning on Tier 3/4, say so. If they tie, say so. If the experiment has flaws that make conclusions uncertain, say so prominently.

The user is making a real business decision based on this output. Give them clean signal, not noise.

Begin.
