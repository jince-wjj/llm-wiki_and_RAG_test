# Blockers

This file is used by the agent to record questions or issues that require user input.
No blockers as of Phase 0 start.

---
## [2026-05-27T16:25:44+08:00] Text validation failed

Downloaded text failed validation:
  - only 3/8 required character names found

### RESOLVED [2026-05-27T16:34:00+08:00]

Root cause: the Project Gutenberg edition (#24264) of 红楼梦 is in **traditional**
Chinese (賈寶玉, 王熙鳳, etc.) while the validator was checking for simplified
forms (贾宝玉, 王熙凤). All 8 names ARE present, just in traditional script.

Fix: added `opencc-python-reimplemented` and convert `t -> s` immediately after
download. The on-disk `raw/hongloumeng_full.txt` is now normalized to simplified
Chinese, matching the variant used by the benchmark and wiki. Validation now
passes (8/8 names). No user action needed.

---
## [2026-05-28T09:14:13+08:00] Phase 3 halted on 3 consecutive failures

Phase 3 halted: 3 consecutive chapter failures.

Failed chapters: 1, 2, 3

Last 3 error messages:
  - ch1: ValueError("All 3 JSON parse attempts failed for tag=ch001. Last error: JSONDecodeError: Expecting ',' delimiter: line 138 column 6 (char 7559)")
  - ch2: ValueError("All 3 JSON parse attempts failed for tag=ch002. Last error: JSONDecodeError: Expecting ',' delimiter: line 146 column 6 (char 7866)")
  - ch3: ValueError("All 3 JSON parse attempts failed for tag=ch003. Last error: JSONDecodeError: Expecting ',' delimiter: line 90 column 6 (char 6509)")

Saved raw responses (inspect these to diagnose the parse drift):
  - wiki/.ingest_logs/parse_failures/ch001_attempt1.txt
  - wiki/.ingest_logs/parse_failures/ch001_attempt2.txt
  - wiki/.ingest_logs/parse_failures/ch001_attempt3.txt
  - wiki/.ingest_logs/parse_failures/ch002_attempt1.txt
  - wiki/.ingest_logs/parse_failures/ch002_attempt2.txt
  - wiki/.ingest_logs/parse_failures/ch002_attempt3.txt
  - wiki/.ingest_logs/parse_failures/ch003_attempt1.txt
  - wiki/.ingest_logs/parse_failures/ch003_attempt2.txt
  - wiki/.ingest_logs/parse_failures/ch003_attempt3.txt

To resume: fix the root cause (in src/api_client.py parsing or the ingest prompt in src/wiki_ingest.py), then re-run `python -m src.wiki_ingest`. Resume is automatic — only chapters with a checkpoint file are skipped.

---
## [2026-05-28T11:12:15+08:00] Phase 3 halted on 3 consecutive failures

Phase 3 halted: 3 consecutive chapter failures.

Failed chapters: 27, 28, 29

Last 3 error messages:
  - ch27: APIConnectionError('Connection error.')
  - ch28: APIConnectionError('Connection error.')
  - ch29: APIConnectionError('Connection error.')

Saved raw responses (inspect these to diagnose the parse drift):
  (no parse_failures files found — see PROGRESS.md for context)

To resume: fix the root cause (in src/api_client.py parsing or the ingest prompt in src/wiki_ingest.py), then re-run `python -m src.wiki_ingest`. Resume is automatic — only chapters with a checkpoint file are skipped.
