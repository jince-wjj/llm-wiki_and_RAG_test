"""LLM-Wiki ingest: iterate chapters 1..80, ask DeepSeek to maintain wiki pages.

For each chapter:
  1. Read chapter text.
  2. Read the existing wiki page index (paths + frontmatter only — cheap).
  3. Identify which existing pages are "relevant" to this chapter (their name
     appears in the chapter body). Load full content for these pages so the
     model can decide CREATE vs UPDATE vs add_contradiction with real context.
  4. Send to DeepSeek with the ingest prompt; receive a JSON action plan.
  5. Apply each action (CREATE writes a fresh file; UPDATE appends a new
     section with a header noting the chapter, so prior content is preserved).
  6. Append to wiki/log.md and save the raw response to wiki/.ingest_logs/.
  7. Update wiki/index.md every 10 chapters.
  8. Write checkpoint and (every 10 chapters) make a git sub-commit.

Per-chapter limits: 20 actions max, 30K input-token soft cap (we truncate the
existing-page list if exceeded).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from . import api_client, config, utils


PAGE_TYPES = ("人物", "地点", "事件", "概念", "综合")
MAX_ACTIONS_PER_CHAPTER = 20
SOFT_TOKEN_CAP = 30_000


# ============================================================================
# Filesystem layer — read/write wiki pages
# ============================================================================


def _safe_path_component(s: str) -> str:
    """Strip characters that could break a filename. Allow CJK + ascii alnum."""
    s = s.strip()
    # Strip directory traversal and shell-unsafe characters
    s = re.sub(r"[\\/\:\*\?\"<>\|\n\r\t]+", "_", s)
    s = s.strip(". ")
    return s[:120]  # cap length


def normalize_page_path(page_path: str) -> Path | None:
    """Convert a model-supplied path like '人物/林黛玉.md' to an absolute path.

    Returns None if path looks malformed.
    """
    page_path = page_path.strip().lstrip("/")
    parts = page_path.split("/")
    if len(parts) != 2:
        return None
    type_dir, fname = parts
    if type_dir not in PAGE_TYPES:
        return None
    if not fname.endswith(".md"):
        fname += ".md"
    fname = _safe_path_component(fname)
    return config.WIKI_DIR / type_dir / fname


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Very small YAML-frontmatter parser. Returns (meta_dict, body_text).

    Accepts simple `key: value` and `key: [a, b, c]` pairs. Anything more
    elaborate falls back to a raw string.
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = text[3:end].strip("\n")
    body = text[end + len("\n---") :].lstrip("\n")
    meta: dict = {}
    for line in fm.splitlines():
        line = line.rstrip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1]
            meta[k] = [
                x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()
            ]
        else:
            meta[k] = v.strip('"').strip("'")
    return meta, body


def format_frontmatter(meta: dict) -> str:
    """Inverse of parse_frontmatter."""
    lines = ["---"]
    for k in ("type", "name", "aliases", "first_appearance", "source_count", "last_updated"):
        if k not in meta:
            continue
        v = meta[k]
        if isinstance(v, list):
            inner = ", ".join(v)
            lines.append(f"{k}: [{inner}]")
        else:
            lines.append(f"{k}: {v}")
    # Include any other keys we don't recognize
    for k, v in meta.items():
        if k in ("type", "name", "aliases", "first_appearance", "source_count", "last_updated"):
            continue
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            lines.append(f"{k}: {v}")
    lines.append("---\n")
    return "\n".join(lines)


def list_existing_pages() -> list[dict]:
    """Scan wiki/ for *.md (excluding index.md/log.md). Return list of dicts."""
    pages = []
    for type_dir in PAGE_TYPES:
        d = config.WIKI_DIR / type_dir
        if not d.exists():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError:
                continue
            meta, body = parse_frontmatter(text)
            rel = f.relative_to(config.WIKI_DIR).as_posix()
            pages.append(
                {
                    "path": rel,
                    "abs_path": f,
                    "type": type_dir,
                    "name": meta.get("name") or f.stem,
                    "aliases": meta.get("aliases") or [],
                    "frontmatter": meta,
                    "body": body,
                    "full_text": text,
                }
            )
    return pages


def relevant_pages_for_chapter(
    pages: list[dict], chapter_text: str, max_pages: int = 10
) -> list[dict]:
    """Return existing pages whose name or aliases appear in the chapter text."""
    hits: list[tuple[int, dict]] = []
    for p in pages:
        score = 0
        if p["name"] and p["name"] in chapter_text:
            score += chapter_text.count(p["name"])
        for alias in p.get("aliases") or []:
            if alias and isinstance(alias, str) and alias in chapter_text:
                score += chapter_text.count(alias)
        if score > 0:
            hits.append((score, p))
    hits.sort(key=lambda x: -x[0])
    return [h[1] for h in hits[:max_pages]]


# ============================================================================
# Prompt construction
# ============================================================================


def build_pages_index_block(pages: list[dict]) -> str:
    """One-liner per page: path | type | name | aliases."""
    if not pages:
        return "(暂无已有页面)"
    lines = []
    for p in pages:
        aliases = p.get("aliases") or []
        aliases_str = ", ".join(aliases) if isinstance(aliases, list) else str(aliases)
        lines.append(
            f"- {p['path']} | {p['type']} | {p['name']}"
            + (f" | aliases: {aliases_str}" if aliases else "")
        )
    return "\n".join(lines)


def build_relevant_pages_block(pages: list[dict], max_chars_per_page: int = 1500) -> str:
    """Full text for relevant pages (truncated)."""
    if not pages:
        return "(本回未涉及已有页面)"
    blocks = []
    for p in pages:
        text = p["full_text"]
        if len(text) > max_chars_per_page:
            text = text[:max_chars_per_page] + "\n[... 已截断 ...]"
        blocks.append(f"=== 已有页面: {p['path']} ===\n{text}")
    return "\n\n".join(blocks)


INGEST_PROMPT = """你是红楼梦 wiki 的维护者。任务是阅读一回内容,然后产出一个"页面操作计划"。

当前 wiki 页面索引(仅路径与基本信息):
{PAGES_INDEX}

本回涉及到的已有页面(全文,供你参考做 UPDATE 或识别矛盾):
{RELEVANT_PAGES}

本次要 ingest 的章节内容:
{CHAPTER_BLOCK}

严格要求:
1. 识别出本回中的主要人物、地点、事件、概念。
2. 对每个实体,决定是 CREATE 新页面还是 UPDATE 已有页面。
3. UPDATE 时,如果新信息与已有内容矛盾,记录到该页面的 `## 矛盾记录` section,不覆盖。
4. 不要对未在本回出现的实体做任何操作。
5. 每个页面必须遵循 schema(参见下文)。
6. content_markdown 中所有事实声明必须紧跟 `[第{N}回]` 引用本回。
7. 单回最多 {MAX_ACTIONS} 个 action,按重要性排序。
8. 输出严格 JSON,不要使用 markdown 代码块包裹。

页面 schema 提示:
- 类型限: 人物 | 地点 | 事件 | 概念 | 综合
- page_path 形如 "人物/林黛玉.md" 或 "事件/葬花.md"
- CREATE 时, content_markdown 必须包含 YAML frontmatter (type/name/aliases/first_appearance/source_count/last_updated) 和该类型必须的 section
- UPDATE 时, content_markdown 是增量内容,会被附加到现有页面末尾;请在内容开头加上一行小标题如 "### 第{N}回更新" 或 "### 矛盾记录 (第{N}回)" 以保留结构

输出格式(纯 JSON):
{{
  "actions": [
    {{
      "operation": "CREATE" | "UPDATE",
      "page_path": "人物/林黛玉.md",
      "page_type": "人物",
      "content_markdown": "...",
      "patch_strategy": "append_section" | "merge_section" | "add_contradiction",
      "reason": "为什么这么操作"
    }}
  ]
}}
"""


def build_ingest_prompt(chapter_id: int, chapter_text: str, all_pages: list[dict]) -> str:
    """Construct the ingest prompt, with truncation if needed."""
    relevant = relevant_pages_for_chapter(all_pages, chapter_text, max_pages=10)
    pages_index_block = build_pages_index_block(all_pages)
    relevant_block = build_relevant_pages_block(relevant)

    chapter_block = f"=== 第{chapter_id}回 ===\n{chapter_text}"

    prompt = INGEST_PROMPT.format(
        N=chapter_id,
        MAX_ACTIONS=MAX_ACTIONS_PER_CHAPTER,
        PAGES_INDEX=pages_index_block,
        RELEVANT_PAGES=relevant_block,
        CHAPTER_BLOCK=chapter_block,
    )

    # Rough token estimate: 1 token ~= 1.5 Chinese chars. If too big, shrink
    # the pages_index_block to bare paths only.
    approx_tokens = len(prompt) / 1.5
    if approx_tokens > SOFT_TOKEN_CAP * 1.3:
        # Drastically shrink pages_index_block
        slim_index = "\n".join(f"- {p['path']}" for p in all_pages)
        prompt = INGEST_PROMPT.format(
            N=chapter_id,
            MAX_ACTIONS=MAX_ACTIONS_PER_CHAPTER,
            PAGES_INDEX=slim_index,
            RELEVANT_PAGES=relevant_block,
            CHAPTER_BLOCK=chapter_block,
        )
    return prompt


# ============================================================================
# Action application
# ============================================================================


def apply_action(action: dict, chapter_id: int, ingest_ts: str) -> dict:
    """Apply one CREATE or UPDATE action. Returns {status, page_path, [reason]}."""
    operation = (action.get("operation") or "").upper()
    page_path = action.get("page_path") or ""
    content = action.get("content_markdown") or ""

    abs_path = normalize_page_path(page_path)
    if abs_path is None:
        return {"status": "skipped", "page_path": page_path, "reason": "invalid path"}
    if not content.strip():
        return {"status": "skipped", "page_path": page_path, "reason": "empty content"}

    abs_path.parent.mkdir(parents=True, exist_ok=True)

    if operation == "CREATE":
        if abs_path.exists():
            # Page now exists (perhaps from a parallel attempt); treat as UPDATE
            return _apply_update(abs_path, content, chapter_id, ingest_ts)
        # Ensure content begins with frontmatter; if not, synthesize one.
        if not content.lstrip().startswith("---"):
            page_type = action.get("page_type") or abs_path.parent.name
            name = abs_path.stem
            fm = format_frontmatter(
                {
                    "type": page_type,
                    "name": name,
                    "aliases": [],
                    "first_appearance": chapter_id,
                    "source_count": 1,
                    "last_updated": ingest_ts,
                }
            )
            content = fm + "\n" + content
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "created", "page_path": str(abs_path.relative_to(config.WIKI_DIR))}

    if operation == "UPDATE":
        if not abs_path.exists():
            # Promote to CREATE
            new_action = {**action, "operation": "CREATE"}
            return apply_action(new_action, chapter_id, ingest_ts)
        return _apply_update(abs_path, content, chapter_id, ingest_ts)

    return {"status": "skipped", "page_path": page_path, "reason": f"unknown op {operation}"}


def _apply_update(abs_path: Path, content: str, chapter_id: int, ingest_ts: str) -> dict:
    """Append `content` to an existing page, with a 'last_updated' frontmatter bump."""
    with open(abs_path, "r", encoding="utf-8") as f:
        existing = f.read()
    meta, body = parse_frontmatter(existing)
    # Update frontmatter
    meta["last_updated"] = ingest_ts
    try:
        meta["source_count"] = int(meta.get("source_count") or 0) + 1
    except (ValueError, TypeError):
        meta["source_count"] = 1

    fm = format_frontmatter(meta)
    # Add a small separator + ingest content
    separator = f"\n\n<!-- ingest: 第{chapter_id}回 @ {ingest_ts} -->\n"
    new_text = fm + "\n" + body.rstrip() + separator + content.strip() + "\n"
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(new_text)
    return {"status": "updated", "page_path": str(abs_path.relative_to(config.WIKI_DIR))}


# ============================================================================
# Index + log maintenance
# ============================================================================


def write_index() -> None:
    """Rewrite wiki/index.md from scratch."""
    pages = list_existing_pages()
    by_type: dict[str, list[dict]] = defaultdict(list)
    for p in pages:
        by_type[p["type"]].append(p)

    lines = [
        "# 红楼梦 LLM-Wiki Index",
        "",
        f"Auto-generated at {utils.now_iso()}. Total pages: {len(pages)}.",
        "",
    ]
    for t in PAGE_TYPES:
        page_list = by_type.get(t, [])
        lines.append(f"## {t} ({len(page_list)})")
        lines.append("")
        for p in sorted(page_list, key=lambda x: x["path"]):
            lines.append(f"- [[{p['path'][:-3]}]] — {p['name']}")
        lines.append("")

    with open(config.WIKI_INDEX_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def append_log(chapter_id: int, pages_touched: int) -> None:
    line = (
        f"## [{utils.now_iso()}] ingest | chapter 第{chapter_id}回 | "
        f"pages touched: {pages_touched}\n"
    )
    utils.append_text(config.WIKI_LOG_MD, line)


# ============================================================================
# Per-chapter ingest
# ============================================================================


def ingest_chapter(chapter_id: int) -> dict:
    """Run one chapter's ingest. Returns a per-chapter summary dict."""
    chapter_path = config.RAW_CHAPTERS_DIR / f"{chapter_id:03d}.txt"
    with open(chapter_path, "r", encoding="utf-8") as f:
        chapter_text = f.read()

    all_pages = list_existing_pages()
    prompt = build_ingest_prompt(chapter_id, chapter_text, all_pages)

    try:
        parsed, result = api_client.chat_complete_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 LLM-Wiki 维护者,擅长结构化中国古典文学知识。"
                        "你的输出必须是严格的 JSON。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            phase="wiki_ingest",
            temperature=0.3,
            max_tokens=8000,
            debug_tag=f"ch{chapter_id:03d}",
        )
    except Exception as e:
        utils.append_progress(
            f"WARN: chapter {chapter_id} ingest call failed: {e!r}"
        )
        return {
            "chapter_id": chapter_id,
            "ok": False,
            "error": repr(e),
            "actions_attempted": 0,
            "actions_applied": 0,
        }

    # Save raw response
    log_path = config.WIKI_INGEST_LOGS_DIR / f"ch{chapter_id:03d}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "chapter_id": chapter_id,
                "input_tokens": result["input_tokens"],
                "output_tokens": result["output_tokens"],
                "latency_ms": result["latency_ms"],
                "parsed_actions": parsed,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    actions = parsed.get("actions") or []
    actions = actions[:MAX_ACTIONS_PER_CHAPTER]

    ts = utils.now_iso()
    results = []
    for action in actions:
        try:
            r = apply_action(action, chapter_id, ts)
            results.append(r)
        except Exception as e:
            results.append(
                {"status": "error", "page_path": action.get("page_path"), "reason": repr(e)}
            )

    applied = sum(1 for r in results if r["status"] in ("created", "updated"))
    append_log(chapter_id, applied)

    summary = {
        "chapter_id": chapter_id,
        "ok": True,
        "actions_attempted": len(actions),
        "actions_applied": applied,
        "creates": sum(1 for r in results if r["status"] == "created"),
        "updates": sum(1 for r in results if r["status"] == "updated"),
        "skipped": sum(1 for r in results if r["status"] in ("skipped", "error")),
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "latency_ms": result["latency_ms"],
    }
    return summary


# ============================================================================
# Phase 3 orchestrator
# ============================================================================


def _git_commit(message: str) -> None:
    """Make a sub-commit. Best-effort: logs failure but doesn't crash."""
    try:
        # Stage
        subprocess.run(
            ["git", "add", "-A"], cwd=config.PROJECT_ROOT, check=True
        )
        # Verify .env is not staged
        diff = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=config.PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        staged = diff.stdout.splitlines()
        if any(s == ".env" or s.endswith("/.env") for s in staged):
            utils.append_blocker(
                "Aborted commit: .env staged",
                f"Staged files included .env: {staged}",
            )
            return
        # Commit
        res = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=config.PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print(f"  [git] committed: {message}", flush=True)
        else:
            # "nothing to commit" is fine; anything else is logged
            out = (res.stdout + res.stderr).lower()
            if "nothing to commit" in out:
                print(f"  [git] nothing to commit", flush=True)
            else:
                utils.append_progress(
                    f"git commit failed for '{message}': {res.stdout} {res.stderr}"
                )
                print(f"  [git] commit FAILED: {res.stderr}", flush=True)
    except Exception as e:
        utils.append_progress(f"git error during commit '{message}': {e!r}")


def already_done_chapter(chapter_id: int) -> bool:
    """Resume support: skip if the chapter has a checkpoint file."""
    return (config.CHECKPOINTS_DIR / f"phase3_ch{chapter_id:03d}.json").exists()


def _halt_with_blocker(failure_history: list[dict], threshold: int) -> None:
    """Write a BLOCKERS.md entry summarising why Phase 3 stopped.

    Lists the failed chapters, their last error messages, and the file paths
    of saved raw responses under wiki/.ingest_logs/parse_failures/ — but
    deliberately does NOT inline the raw bodies (they can be huge).
    """
    chapter_list = ", ".join(str(fh["chapter_id"]) for fh in failure_history)
    error_lines = "\n".join(
        f"  - ch{fh['chapter_id']}: {fh['error'][:500]}" for fh in failure_history
    )
    parse_failure_dir = config.WIKI_INGEST_LOGS_DIR / "parse_failures"
    raw_paths: list[str] = []
    for fh in failure_history:
        tag = f"ch{fh['chapter_id']:03d}"
        for k in range(1, 6):  # check more than max_retries in case it grows
            p = parse_failure_dir / f"{tag}_attempt{k}.txt"
            if p.exists():
                raw_paths.append(str(p.relative_to(config.PROJECT_ROOT)))
    raw_paths_block = (
        "\n".join(f"  - {p}" for p in raw_paths)
        if raw_paths
        else "  (no parse_failures files found — see PROGRESS.md for context)"
    )
    body = (
        f"Phase 3 halted: {threshold} consecutive chapter failures.\n\n"
        f"Failed chapters: {chapter_list}\n\n"
        f"Last {len(failure_history)} error messages:\n{error_lines}\n\n"
        f"Saved raw responses (inspect these to diagnose the parse drift):\n"
        f"{raw_paths_block}\n\n"
        f"To resume: fix the root cause (in src/api_client.py parsing or the "
        f"ingest prompt in src/wiki_ingest.py), then re-run "
        f"`python -m src.wiki_ingest`. Resume is automatic — only chapters "
        f"with a checkpoint file are skipped."
    )
    utils.append_blocker(
        f"Phase 3 halted on {threshold} consecutive failures", body
    )
    print(
        f"Phase 3 HALTED: {threshold} consecutive failures "
        f"(chapters {chapter_list}). See BLOCKERS.md.",
        flush=True,
    )


def run() -> None:
    if not utils.checkpoint_exists("phase2_done"):
        print("Phase 2 not complete — refusing to run Phase 3.", file=sys.stderr)
        sys.exit(2)

    print("Phase 3: LLM-Wiki ingest of 80 chapters", flush=True)
    utils.append_progress("Phase 3 started: LLM-Wiki ingest")

    # Ensure wiki subdirs exist
    for t in PAGE_TYPES:
        (config.WIKI_DIR / t).mkdir(parents=True, exist_ok=True)
    config.WIKI_INGEST_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    if not config.WIKI_LOG_MD.exists():
        with open(config.WIKI_LOG_MD, "w", encoding="utf-8") as f:
            f.write("# LLM-Wiki Ingest Log\n\n")

    total_summary = {
        "chapters_ingested": 0,
        "actions_applied": 0,
        "creates": 0,
        "updates": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }

    consecutive_failures = 0
    failure_history: list[dict] = []  # rolling, keeps last MAX_CONSECUTIVE_FAILURES
    actions_applied_in_window = 0
    MAX_CONSECUTIVE_FAILURES = 3

    for ch in range(1, 81):
        if already_done_chapter(ch):
            print(f"  ch{ch}: already done, skipping (resume)", flush=True)
            continue

        print(f"  ch{ch}: ingesting...", flush=True)
        summary = ingest_chapter(ch)

        # A chapter only counts as "success" when the API call returned AND at
        # least one wiki page was actually created/updated. This prevents the
        # earlier failure mode where the model returned a parseable but empty
        # action list — or where the parse failed entirely — and the loop wrote
        # a tiny "fake" checkpoint that masked the failure on resume.
        success = bool(summary.get("ok")) and summary.get("actions_applied", 0) >= 1

        if success:
            utils.write_json(
                config.CHECKPOINTS_DIR / f"phase3_ch{ch:03d}.json", summary
            )
            print(
                f"  ch{ch}: applied={summary['actions_applied']} "
                f"(C={summary['creates']} U={summary['updates']} S={summary['skipped']}) "
                f"tokens={summary['input_tokens']}+{summary['output_tokens']}",
                flush=True,
            )
            total_summary["chapters_ingested"] += 1
            total_summary["actions_applied"] += summary["actions_applied"]
            total_summary["creates"] += summary["creates"]
            total_summary["updates"] += summary["updates"]
            total_summary["input_tokens"] += summary["input_tokens"]
            total_summary["output_tokens"] += summary["output_tokens"]
            actions_applied_in_window += summary["actions_applied"]
            consecutive_failures = 0
        else:
            err = summary.get("error") or (
                "ok=True but actions_applied=0 (model returned no usable actions)"
            )
            print(f"  ch{ch}: FAILED - {err}", flush=True)
            utils.append_progress(f"Phase 3 chapter {ch} failed: {err}")
            consecutive_failures += 1
            failure_history.append({"chapter_id": ch, "error": err})
            failure_history = failure_history[-MAX_CONSECUTIVE_FAILURES:]

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                _halt_with_blocker(failure_history, MAX_CONSECUTIVE_FAILURES)
                write_index()
                return

        # Every 10 chapters: update index + (conditionally) sub-commit
        if ch % 10 == 0:
            write_index()
            if actions_applied_in_window > 0:
                start_ch = ch - 9
                _git_commit(f"phase3: ingested chapters {start_ch}-{ch}")
            else:
                print(
                    f"  [git] window {ch-9}-{ch}: no actions applied, skipping sub-commit",
                    flush=True,
                )
            actions_applied_in_window = 0

    # Final index regen
    write_index()

    pages = list_existing_pages()
    by_type_counts = defaultdict(int)
    for p in pages:
        by_type_counts[p["type"]] += 1

    utils.write_checkpoint(
        "phase3_done",
        {
            **total_summary,
            "total_pages": len(pages),
            "by_type": dict(by_type_counts),
        },
    )
    utils.add_phase_complete("phase3")
    utils.append_progress(
        f"Phase 3 complete: {total_summary['chapters_ingested']} chapters ingested, "
        f"{len(pages)} pages total ({dict(by_type_counts)})"
    )
    print(
        f"Phase 3 complete: {len(pages)} pages across types {dict(by_type_counts)}",
        flush=True,
    )


if __name__ == "__main__":
    run()
