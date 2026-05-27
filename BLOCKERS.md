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
