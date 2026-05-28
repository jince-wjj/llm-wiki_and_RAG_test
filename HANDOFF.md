# Handoff to Evaluation Agent (Agent 2)

## What was done
- 红楼梦 前80回 ingested as LLM-Wiki with schema in `CLAUDE.md`.
- Same 80 chapters chunked + embedded as RAG baseline.
- 100 benchmark questions across 4 tiers in `benchmark/questions.json`.
- Ground truth in `benchmark/ground_truth.json`.
- LLM-Wiki answers in `results/wiki_answers.json`.
- RAG baseline answers in `results/rag_answers.json`.
- Aggregate stats in `results/stats.json` (tokens, latency, per-tier breakdown).

## What you need to do
1. Read `EVALUATION_INSTRUCTIONS.md` (provided separately by the user).
2. Score every answer in both files against ground truth.
3. Compute aggregate metrics broken down by tier.
4. Generate the final comparison report.

## Critical constraints for evaluation
- You MUST use a DIFFERENT model from the one that generated answers (deepseek-chat). Recommended: claude-opus-4-7 or gpt-5.
- You MUST score blind to system source — randomize order, hide which system produced which answer until aggregation.
- You MUST NOT modify any file in `wiki/`, `rag_baseline/`, `results/`, `benchmark/` except to append to logs.
- Output your evaluation to `evaluation/` directory.

## Files Agent 2 should produce
- `evaluation/scores.json`: per-question scores for both systems.
- `evaluation/final_report.md`: aggregate comparison, per-tier breakdown, notable observations.

## Quick reference: what's in the box

| File | Shape | Notes |
|---|---|---|
| `benchmark/questions.json` | array of 100 `{question_id, question, tier}` | inputs fed to both systems |
| `benchmark/ground_truth.json` | parallel array of 100 `{question_id, ground_truth, source_chapter_ids, source_evidence, confidence}` | reference answers — DO NOT show to systems |
| `results/wiki_answers.json` | 100 × `{question_id, question, tier, answer, retrieved_page_paths, entities_extracted, input_tokens, output_tokens, latency_ms}` | LLM-Wiki system output |
| `results/rag_answers.json` | 100 × `{question_id, question, tier, answer, retrieved_chunk_ids, retrieved_chapter_ids, input_tokens, output_tokens, latency_ms}` | RAG baseline output |
| `results/stats.json` | aggregate token/latency/answer-length stats with per-tier breakdown | summary for the report |
| `wiki/` | 448 markdown pages (291 人物 / 49 地点 / 61 事件 / 47 概念) | what the wiki system retrieved over |
| `rag_baseline/chunks.jsonl` | 1573 chunks of ~500 chars with 100 overlap | what the RAG baseline retrieved over |

## Models used (frozen — do not change for evaluation)

| Purpose | Model | API |
|---|---|---|
| Wiki ingest | `deepseek-chat` | DeepSeek |
| Wiki query answer | `deepseek-chat` | DeepSeek |
| RAG baseline answer | `deepseek-chat` | DeepSeek |
| Benchmark gen | `deepseek-chat` | DeepSeek |
| Embedding (RAG + wiki search) | `BAAI/bge-m3` | SiliconFlow |

Wiki-query and RAG-query share the same generator model so the comparison measures the *retrieval paradigm*, not the *generator*.
