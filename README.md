# 红楼梦 LLM-Wiki vs RAG — experiment artifacts

A controlled comparison of the **LLM-Wiki paradigm** against a **vanilla RAG baseline** on the first 80 chapters of 《红楼梦》(Dream of the Red Chamber).

Both systems answer the same 100-question benchmark using the same generator model (`deepseek-chat`). Only the retrieval mechanism differs:
- **RAG baseline**: 500-char chunks with 100-char overlap, BGE-M3 embeddings, top-5 retrieval, naive prompt.
- **LLM-Wiki**: structured Markdown pages (people / places / events / concepts) authored by the same LLM during ingest, retrieved by entity-extraction + BGE-M3 vector search over page headers.

This repository contains everything Agent 2 needs to evaluate the two systems. **Agent 1 (this repo) does NOT score answers** — that's Agent 2's job.

## Directory tour

| Path | Purpose |
|---|---|
| `AGENT_INSTRUCTIONS.md` | full spec for Agent 1 (Builder & Runner) |
| `CLAUDE.md` | LLM-Wiki page schema (page types, frontmatter, citation rules) |
| `HANDOFF.md` | what Agent 2 receives and what they must produce |
| `MANIFEST.json` | experiment metadata (model IDs, scope, phases completed) |
| `PROGRESS.md` | append-only run log |
| `BLOCKERS.md` | issues encountered during the run (all RESOLVED at handoff time) |
| `usage.json` | cumulative API token usage and cost |
| `raw/chapters/001..080.txt` | source chapter text (simplified Chinese) |
| `benchmark/questions.json` | 100 questions across 4 tiers (single-fact / single-source-synth / cross-source-synth / conflict) |
| `benchmark/ground_truth.json` | reference answers + cited chapters + evidence excerpts |
| `wiki/` | the LLM-Wiki: 448 Markdown pages, `index.md`, append-only `log.md` |
| `rag_baseline/chunks.jsonl` | the RAG corpus (1573 chunks) |
| `rag_baseline/README.md` | implementation notes for the baseline |
| `rag_baseline/chroma_db/` | ChromaDB persistent index (gitignored — regenerable from chunks.jsonl) |
| `results/wiki_answers.json` | LLM-Wiki's 100 answers |
| `results/rag_answers.json` | RAG baseline's 100 answers |
| `results/stats.json` | aggregate stats per system + per-tier breakdown |
| `src/` | implementation (all phases) |
| `checkpoints/` | per-phase / per-chapter resume markers |

## Reproducing or extending

```bash
cp .env.example .env       # fill DEEPSEEK_API_KEY and SILICONFLOW_API_KEY
pip install -r requirements.txt
python -m src.run_experiment   # resumes from latest checkpoint
```

The orchestrator is idempotent. Each phase writes a checkpoint at completion; on restart, completed phases are skipped. Within Phase 3 (wiki ingest), each chapter has its own checkpoint so a partial ingest resumes at the next un-ingested chapter.

## Headline numbers (for reference — Agent 2 will compute the real metrics)

- 80 chapters ingested → 448 wiki pages (291 人物 / 49 地点 / 61 事件 / 47 概念)
- 1573 RAG chunks indexed
- 100 benchmark questions, 100/100 answers from each system (no empties)
- Total API spend: **$1.82** (within the $15 cap)

## Where to go next

- Agent 2: read `HANDOFF.md`, then start evaluation following `EVALUATION_INSTRUCTIONS.md`.
- A human inspecting results: open `results/stats.json` for the at-a-glance comparison, then sample-read entries from both `wiki_answers.json` and `rag_answers.json` side-by-side.
