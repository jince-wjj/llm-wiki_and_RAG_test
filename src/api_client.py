"""Thin wrappers around DeepSeek (chat) and SiliconFlow (embedding) clients.

Both endpoints are OpenAI-compatible. Retries are handled via tenacity on
network errors and on 429/5xx status codes. 4xx (other than 429) raise
immediately — these are config errors and must trigger a BLOCKER.
"""

from __future__ import annotations

import json
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


def chat_complete_json(**kwargs) -> tuple[dict, dict]:
    """Wrapper that requests JSON and parses it. Returns (parsed_obj, raw_result).

    Falls back to extracting the largest {...} block if response isn't pure JSON.
    """
    kwargs.setdefault("response_format", {"type": "json_object"})
    result = chat_complete(**kwargs)
    content = result["content"]
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        # Try to recover by finding the first { ... last }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(content[start : end + 1])
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Could not parse JSON response: {e}\nContent: {content[:500]}"
                )
        else:
            raise ValueError(f"No JSON object in response: {content[:500]}")
    return parsed, result


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
