"""Common utilities: usage tracking, progress logging, JSON IO."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from . import config


def now_iso() -> str:
    """Return current time as ISO-8601 in Asia/Shanghai (+08:00)."""
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)


def append_progress(line: str) -> None:
    """Append a timestamped line to PROGRESS.md."""
    append_text(config.PROGRESS_MD, f"\n## [{now_iso()}] {line}\n")


def append_blocker(title: str, body: str) -> None:
    """Append a blocker entry to BLOCKERS.md."""
    block = f"\n---\n## [{now_iso()}] {title}\n\n{body}\n"
    append_text(config.BLOCKERS_MD, block)


def update_usage(
    *,
    phase: str,
    input_tokens: int,
    output_tokens: int,
    is_embedding: bool = False,
) -> dict:
    """Atomically update usage.json and return current totals.

    Embedding calls (SiliconFlow free tier) contribute 0 cost but tokens are logged.
    """
    if config.USAGE_JSON.exists():
        usage = read_json(config.USAGE_JSON)
    else:
        usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "estimated_cost_usd": 0.0,
            "calls": 0,
            "by_phase": {},
        }

    usage["total_input_tokens"] += input_tokens
    usage["total_output_tokens"] += output_tokens
    usage["calls"] += 1

    if not is_embedding:
        cost = (
            input_tokens * config.COST_DEEPSEEK_INPUT_PER_M / 1_000_000
            + output_tokens * config.COST_DEEPSEEK_OUTPUT_PER_M / 1_000_000
        )
        usage["estimated_cost_usd"] = round(
            usage.get("estimated_cost_usd", 0.0) + cost, 6
        )

    by_phase = usage.setdefault("by_phase", {})
    p = by_phase.setdefault(
        phase,
        {"input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": 0.0},
    )
    p["input_tokens"] += input_tokens
    p["output_tokens"] += output_tokens
    p["calls"] += 1
    if not is_embedding:
        p["cost_usd"] = round(p["cost_usd"] + cost, 6)

    write_json(config.USAGE_JSON, usage)
    return usage


def check_budget() -> None:
    """Raise BudgetExceeded if estimated cost has crossed the cap."""
    if not config.USAGE_JSON.exists():
        return
    usage = read_json(config.USAGE_JSON)
    if usage.get("estimated_cost_usd", 0.0) >= config.BUDGET_CAP_USD:
        msg = (
            f"BUDGET CAP HIT\n"
            f"Estimated cost: ${usage['estimated_cost_usd']:.4f}\n"
            f"Cap: ${config.BUDGET_CAP_USD}\n"
            f"Awaiting user authorization to continue."
        )
        append_blocker("Budget cap reached", msg)
        raise BudgetExceeded(msg)


class BudgetExceeded(RuntimeError):
    pass


def write_checkpoint(name: str, data: dict | None = None) -> None:
    """Write a checkpoint marker to checkpoints/<name>."""
    path = config.CHECKPOINTS_DIR / name
    payload = {"completed_at": now_iso()}
    if data:
        payload.update(data)
    write_json(path if name.endswith(".json") else path.with_suffix(".json"), payload)
    # Also write a sentinel file with the bare name for easy `ls` discovery
    if not name.endswith(".json"):
        with open(config.CHECKPOINTS_DIR / name, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False))


def checkpoint_exists(name: str) -> bool:
    return (config.CHECKPOINTS_DIR / name).exists()


def update_manifest(updates: dict) -> dict:
    manifest = read_json(config.MANIFEST_JSON)
    manifest.update(updates)
    write_json(config.MANIFEST_JSON, manifest)
    return manifest


def add_phase_complete(phase: str) -> None:
    manifest = read_json(config.MANIFEST_JSON)
    completed = manifest.setdefault("phases_completed", [])
    if phase not in completed:
        completed.append(phase)
    write_json(config.MANIFEST_JSON, manifest)


class Timer:
    """Context manager that measures elapsed wall time in milliseconds."""

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = int((time.perf_counter() - self._t0) * 1000)
