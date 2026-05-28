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
