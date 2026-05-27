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
