# Progress Log — 红楼梦 LLM-Wiki vs RAG Experiment

This file is append-only. Each entry is timestamped.

---

## [2026-05-27T15:53:00+08:00] Phase 0 started

Bootstrapping directory structure and config templates.

## [2026-05-27T16:25:29+08:00] Phase 1 started: data acquisition

## [2026-05-27T16:28:34+08:00] Phase 1 started: data acquisition

## [2026-05-27T16:28:50+08:00] Phase 1 complete: {'chapters_written': 80, 'total_chars': 640491, 'min_chapter_len': 4602, 'max_chapter_len': 12676, 'avg_chapter_len': 8006}

## [2026-05-27T16:31:46+08:00] Phase 1 started: data acquisition

## [2026-05-27T16:31:46+08:00] Phase 1 complete: {'chapters_written': 80, 'total_chars': 620308, 'min_chapter_len': 4463, 'max_chapter_len': 12304, 'avg_chapter_len': 7753}

## [2026-05-27T16:32:47+08:00] Phase 1 started: data acquisition

## [2026-05-27T16:32:47+08:00] Phase 1 complete: {'chapters_written': 80, 'total_chars': 620308, 'min_chapter_len': 4463, 'max_chapter_len': 12304, 'avg_chapter_len': 7753}

## [2026-05-27T16:33:35+08:00] Phase 1 detail: 2 chapters slightly below 5,000-char lower bound from instructions (ch79=4,463; ch78=4,602? — actually ch[*] short ones; see sources.csv). These are the genuine chapter lengths in the Project Gutenberg edition; the parser is correct. Proceeding under section-4.4 "log and continue" policy.

## [2026-05-27T16:38:19+08:00] Source data note: the Project Gutenberg edition has 348 □ placeholder characters across 68 chapters (0.056% of total text) where rare characters did not survive the original encoding. Self-validation will catch hallucinations around these gaps. Both Wiki and RAG operate on identical text, so the comparison is unaffected.

## [2026-05-27T16:38:28+08:00] Phase 2 started: benchmark generation

## [2026-05-27T16:47:04+08:00] Phase 2 started: benchmark generation

## [2026-05-27T16:58:02+08:00] Phase 2 complete: 100 questions across 4 tiers

## [2026-05-28T09:09:23+08:00] Phase 3 started: LLM-Wiki ingest

## [2026-05-28T09:09:52+08:00] JSON parse failure (tag=ch001, attempt=1/3): JSONDecodeError: Expecting ',' delimiter: line 146 column 6 (char 7843)

## [2026-05-28T09:10:21+08:00] JSON parse failure (tag=ch001, attempt=2/3): JSONDecodeError: Expecting ',' delimiter: line 130 column 6 (char 7426)

## [2026-05-28T09:10:49+08:00] JSON parse failure (tag=ch001, attempt=3/3): JSONDecodeError: Expecting ',' delimiter: line 138 column 6 (char 7559)

## [2026-05-28T09:10:49+08:00] WARN: chapter 1 ingest call failed: ValueError("All 3 JSON parse attempts failed for tag=ch001. Last error: JSONDecodeError: Expecting ',' delimiter: line 138 column 6 (char 7559)")

## [2026-05-28T09:10:49+08:00] Phase 3 chapter 1 failed: ValueError("All 3 JSON parse attempts failed for tag=ch001. Last error: JSONDecodeError: Expecting ',' delimiter: line 138 column 6 (char 7559)")

## [2026-05-28T09:11:18+08:00] JSON parse failure (tag=ch002, attempt=1/3): JSONDecodeError: Expecting ',' delimiter: line 154 column 6 (char 7763)

## [2026-05-28T09:11:47+08:00] JSON parse failure (tag=ch002, attempt=2/3): JSONDecodeError: Expecting ',' delimiter: line 146 column 6 (char 7786)

## [2026-05-28T09:12:14+08:00] JSON parse failure (tag=ch002, attempt=3/3): JSONDecodeError: Expecting ',' delimiter: line 146 column 6 (char 7866)

## [2026-05-28T09:12:14+08:00] WARN: chapter 2 ingest call failed: ValueError("All 3 JSON parse attempts failed for tag=ch002. Last error: JSONDecodeError: Expecting ',' delimiter: line 146 column 6 (char 7866)")

## [2026-05-28T09:12:14+08:00] Phase 3 chapter 2 failed: ValueError("All 3 JSON parse attempts failed for tag=ch002. Last error: JSONDecodeError: Expecting ',' delimiter: line 146 column 6 (char 7866)")

## [2026-05-28T09:12:43+08:00] JSON parse failure (tag=ch003, attempt=1/3): JSONDecodeError: Expecting ',' delimiter: line 98 column 6 (char 6822)

## [2026-05-28T09:13:13+08:00] JSON parse failure (tag=ch003, attempt=2/3): JSONDecodeError: Expecting ',' delimiter: line 90 column 6 (char 6586)

## [2026-05-28T09:14:13+08:00] JSON parse failure (tag=ch003, attempt=3/3): JSONDecodeError: Expecting ',' delimiter: line 90 column 6 (char 6509)

## [2026-05-28T09:14:13+08:00] WARN: chapter 3 ingest call failed: ValueError("All 3 JSON parse attempts failed for tag=ch003. Last error: JSONDecodeError: Expecting ',' delimiter: line 90 column 6 (char 6509)")

## [2026-05-28T09:14:13+08:00] Phase 3 chapter 3 failed: ValueError("All 3 JSON parse attempts failed for tag=ch003. Last error: JSONDecodeError: Expecting ',' delimiter: line 90 column 6 (char 6509)")

## [2026-05-28T10:55:42+08:00] Phase 3 started: LLM-Wiki ingest

## [2026-05-28T11:11:55+08:00] WARN: chapter 27 ingest call failed: APIConnectionError('Connection error.')

## [2026-05-28T11:11:55+08:00] Phase 3 chapter 27 failed: APIConnectionError('Connection error.')

## [2026-05-28T11:12:04+08:00] WARN: chapter 28 ingest call failed: APIConnectionError('Connection error.')

## [2026-05-28T11:12:04+08:00] Phase 3 chapter 28 failed: APIConnectionError('Connection error.')

## [2026-05-28T11:12:15+08:00] WARN: chapter 29 ingest call failed: APIConnectionError('Connection error.')

## [2026-05-28T11:12:15+08:00] Phase 3 chapter 29 failed: APIConnectionError('Connection error.')

## [2026-05-28T11:16:49+08:00] Phase 3 started: LLM-Wiki ingest

## [2026-05-28T11:54:27+08:00] Phase 3 complete: 54 chapters ingested, 448 pages total ({'人物': 291, '地点': 49, '事件': 61, '概念': 47})

## [2026-05-28T11:54:27+08:00] Phase 4 started: RAG baseline build

## [2026-05-28T11:55:49+08:00] Phase 4 complete: 1573 chunks embedded and indexed

## [2026-05-28T11:55:49+08:00] Phase 5.1 started: RAG baseline answering

## [2026-05-28T12:00:17+08:00] Phase 5.2 started: LLM-Wiki answering

## [2026-05-28T12:08:00+08:00] All phases complete

Agent 1 (Builder & Runner) finished all 6 phases:
- Phase 1: 80 chapters acquired and validated
- Phase 2: 100-question benchmark across 4 tiers
- Phase 3: LLM-Wiki ingest — 448 pages (291 人物, 49 地点, 61 事件, 47 概念)
- Phase 4: RAG baseline — 1573 chunks embedded with BGE-M3
- Phase 5: RAG baseline answered all 100 questions
- Phase 6: LLM-Wiki answered all 100 questions

Outputs: results/wiki_answers.json, results/rag_answers.json, results/stats.json.
Total API spend: $1.82 (under $15 cap).
Stats highlight (computed in results/stats.json):
  Wiki: 100 answers, avg 117 chars, avg latency 2733 ms.
  RAG : 100 answers, avg 118 chars, avg latency 2159 ms.

Notable incidents during the run (all recovered, see BLOCKERS.md):
1. Phase 3 first attempt halted at ch1-3 (output truncation at max_tokens=4000).
   Fixed by bumping max_tokens to 8000 + adding explicit finish_reason=='length'
   detection in api_client.chat_complete_json. Commit be2ac9f.
2. Phase 3 second attempt halted at ch27-29 (APIConnectionError, transient).
   Fixed by bumping tenacity stop_after_attempt 3 -> 8 in _chat_with_retry,
   giving ~3 minutes of patient retry per API call. Commit add68e2.

Ready for Agent 2 (Evaluator). See HANDOFF.md.
