"""Thin wrappers around DeepSeek (chat) and SiliconFlow (embedding) clients.

Both endpoints are OpenAI-compatible. Retries are handled via tenacity on
network errors and on 429/5xx status codes. 4xx (other than 429) raise
immediately — these are config errors and must trigger a BLOCKER.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, List, Sequence

from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from openai import InternalServerError
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from . import config, utils


_RETRYABLE = (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)


class APIFatal(RuntimeError):
    """4xx config error — should never be retried, should surface to BLOCKERS."""


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type(_RETRYABLE),
)
def _chat_with_retry(**kwargs):
    return config.deepseek_client.chat.completions.create(**kwargs)


def chat_complete(
    *,
    messages: list[dict],
    phase: str,
    model: str = config.MODEL_ANSWER,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    response_format: dict | None = None,
    timeout: float = 120.0,
) -> dict:
    """Call DeepSeek chat. Returns dict with content, usage, latency_ms."""
    kwargs: dict[str, Any] = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    if response_format is not None:
        kwargs["response_format"] = response_format

    t0 = time.perf_counter()
    try:
        resp = _chat_with_retry(**kwargs)
    except APIError as e:
        status = getattr(e, "status_code", None)
        if status in (400, 401, 403, 404):
            utils.append_blocker(
                f"DeepSeek fatal {status}",
                f"Non-retryable API error: {e!r}\nphase={phase}",
            )
            raise APIFatal(f"DeepSeek {status}: {e}") from e
        raise
    latency_ms = int((time.perf_counter() - t0) * 1000)

    content = resp.choices[0].message.content or ""
    usage = resp.usage
    input_tokens = getattr(usage, "prompt_tokens", 0)
    output_tokens = getattr(usage, "completion_tokens", 0)

    utils.update_usage(
        phase=phase,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        is_embedding=False,
    )
    utils.check_budget()

    return {
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "finish_reason": resp.choices[0].finish_reason,
    }


# ---------------------------------------------------------------------------
# Robust JSON parsing for model output
# ---------------------------------------------------------------------------

# Single-quoted-KEY matcher: a single-quoted token in key position, i.e.
# preceded by `{` or `,` (with optional whitespace) and followed by `:`.
# Only keys that contain no embedded quotes or backslashes are rewritten,
# which keeps the substitution conservative — single quotes inside string
# values (English contractions, Chinese 引号, etc.) are NOT touched.
_KEY_QUOTE_RE = re.compile(r"([\{,]\s*)'([^'\\\n\r]+)'(\s*:)")


def _strip_fences(s: str) -> str:
    """Remove a leading/trailing ```json ... ``` markdown fence if present."""
    s = s.strip()
    if not s.startswith("```"):
        return s
    first_nl = s.find("\n")
    if first_nl == -1:
        return s
    inner = s[first_nl + 1 :].rstrip()
    if inner.endswith("```"):
        inner = inner[:-3].rstrip()
    return inner


def _looks_like_json_object(s: str) -> bool:
    """Quick structural sniff before we try the more aggressive key-quote fix."""
    s = s.strip()
    return bool(s) and s[0] == "{" and "}" in s and ":" in s


def _fix_key_position_quotes(s: str) -> str:
    """Replace single-quoted keys with double-quoted keys.

    Conservative: only touches `'foo':` patterns where `'foo'` immediately
    follows `{` or `,`. Single quotes inside string values are left alone.
    """
    return _KEY_QUOTE_RE.sub(r'\1"\2"\3', s)


def _robust_parse_json(content: str) -> Any:
    """Parse `content` as JSON, tolerating common LLM output deviations.

    Strategy (in order, first to succeed wins):
      1. Strip whitespace, parse as-is.
      2. Strip ```json ... ``` markdown fences, parse.
      3. Extract the outermost {...} block via brace-find/rfind (handles
         leading prose like "好的，下面是 JSON：").
      4. If the extracted candidate still structurally looks like a JSON
         object, apply key-position single→double quote substitution and
         parse.

    Raises the LAST `json.JSONDecodeError` if all steps fail (preserved so
    the caller can chain it).
    """
    if not isinstance(content, str):
        raise json.JSONDecodeError("Content is not a string", str(content), 0)
    stripped = content.strip()
    if not stripped:
        raise json.JSONDecodeError("Empty content", content, 0)

    last_err: json.JSONDecodeError | None = None

    # 1. raw
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        last_err = e

    # 2. unfenced
    unfenced = _strip_fences(stripped)
    if unfenced and unfenced != stripped:
        try:
            return json.loads(unfenced)
        except json.JSONDecodeError as e:
            last_err = e

    # 3. brace-balanced extraction
    candidate = unfenced or stripped
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        extracted = candidate[start : end + 1]
        try:
            return json.loads(extracted)
        except json.JSONDecodeError as e:
            last_err = e
    else:
        extracted = candidate

    # 4. conservative key-position single→double quote fix
    if _looks_like_json_object(extracted):
        fixed = _fix_key_position_quotes(extracted)
        if fixed != extracted:
            try:
                return json.loads(fixed)
            except json.JSONDecodeError as e:
                last_err = e

    assert last_err is not None
    raise last_err


_JSON_STRICTER_DIRECTIVE = (
    "\n\nIMPORTANT: Output ONLY valid JSON. No markdown fences. "
    "No explanation. No prose. JSON only."
)


def chat_complete_json(
    *,
    messages: list[dict],
    phase: str,
    model: str = config.MODEL_ANSWER,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    response_format: dict | None = None,
    timeout: float = 120.0,
    debug_tag: str | None = None,
    max_retries: int = 3,
) -> tuple[dict, dict]:
    """Call DeepSeek for a JSON response, with retries on parse failure.

    Args:
      messages, phase, model, temperature, max_tokens, response_format, timeout:
        forwarded to `chat_complete`.
      debug_tag: optional tag (e.g. "ch023") used to name raw-response dumps
        on parse failure. Files land in
        `wiki/.ingest_logs/parse_failures/<debug_tag>_attempt<K>.txt`.
      max_retries: total attempts allowed before giving up (default 3).

    Retry escalation:
      - Attempt 2: append a stricter directive ("JSON only, no fences, no
        prose") to the last user message.
      - Attempt 3+: also force temperature=0.0.

    Returns (parsed_obj, raw_result_of_last_attempt).
    Raises ValueError chained from the last `json.JSONDecodeError` if every
    attempt fails. Original decode error is preserved as `__cause__`.
    """
    if response_format is None:
        response_format = {"type": "json_object"}

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        attempt_messages: list[dict] = [dict(m) for m in messages]
        attempt_temp = temperature
        if attempt >= 2:
            for i in range(len(attempt_messages) - 1, -1, -1):
                if attempt_messages[i].get("role") == "user":
                    attempt_messages[i] = {
                        **attempt_messages[i],
                        "content": attempt_messages[i]["content"]
                        + _JSON_STRICTER_DIRECTIVE,
                    }
                    break
        if attempt >= 3:
            attempt_temp = 0.0

        result = chat_complete(
            messages=attempt_messages,
            phase=phase,
            model=model,
            temperature=attempt_temp,
            max_tokens=max_tokens,
            response_format=response_format,
            timeout=timeout,
        )
        content = result["content"] or ""

        try:
            parsed = _robust_parse_json(content)
            return parsed, result
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if debug_tag:
                try:
                    fail_dir = config.WIKI_INGEST_LOGS_DIR / "parse_failures"
                    fail_dir.mkdir(parents=True, exist_ok=True)
                    fail_path = fail_dir / f"{debug_tag}_attempt{attempt}.txt"
                    fail_path.write_text(
                        f"=== attempt {attempt} of {max_retries} ===\n"
                        f"error: {type(e).__name__}: {e}\n"
                        f"phase: {phase}\n"
                        f"temperature: {attempt_temp}\n"
                        f"input_tokens: {result.get('input_tokens')}\n"
                        f"output_tokens: {result.get('output_tokens')}\n"
                        f"finish_reason: {result.get('finish_reason')}\n\n"
                        f"=== raw content ===\n{content}\n",
                        encoding="utf-8",
                    )
                except OSError:
                    pass
            utils.append_progress(
                f"JSON parse failure (tag={debug_tag}, "
                f"attempt={attempt}/{max_retries}): "
                f"{type(e).__name__}: {str(e)[:200]}"
            )

    raise ValueError(
        f"All {max_retries} JSON parse attempts failed"
        + (f" for tag={debug_tag}" if debug_tag else "")
        + f". Last error: {type(last_error).__name__}: {last_error}"
    ) from last_error


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    retry=retry_if_exception_type(_RETRYABLE),
)
def _embed_with_retry(inputs: Sequence[str]):
    return config.siliconflow_client.embeddings.create(
        model=config.MODEL_EMBEDDING, input=list(inputs)
    )


def embed(inputs: Sequence[str], *, phase: str) -> List[List[float]]:
    """Embed a batch of strings via SiliconFlow BGE-M3. Returns list of vectors."""
    if not inputs:
        return []
    try:
        resp = _embed_with_retry(inputs)
    except APIError as e:
        status = getattr(e, "status_code", None)
        if status in (400, 401, 403, 404):
            utils.append_blocker(
                f"SiliconFlow fatal {status}",
                f"Non-retryable API error: {e!r}\nphase={phase}",
            )
            raise APIFatal(f"SiliconFlow {status}: {e}") from e
        raise

    vectors = [d.embedding for d in resp.data]
    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    utils.update_usage(
        phase=phase,
        input_tokens=input_tokens,
        output_tokens=0,
        is_embedding=True,
    )
    return vectors


def ping_deepseek() -> dict:
    """1-token sanity check."""
    return chat_complete(
        messages=[{"role": "user", "content": "ping"}],
        phase="ping",
        max_tokens=1,
        temperature=0.0,
    )


def ping_siliconflow() -> int:
    """Single embedding sanity check. Returns vector dimension."""
    vecs = embed(["hello"], phase="ping")
    return len(vecs[0])
