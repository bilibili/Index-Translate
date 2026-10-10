"""OpenAI-compatible Judge client with a durable append-only cache.

Two request shapes, chosen by model name. Reasoning models are served on
``/responses`` instead of ``/chat/completions`` -- on the gateway this benchmark
was scored with, a ``gpt-5.x`` model has no chat/completions cluster at all, so
sending one there fails rather than falling back -- and they take an output-token
budget and a reasoning effort in place of a temperature. Everything else uses
``/chat/completions``.
"""

from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from pathlib import Path
from typing import Callable

# Chat models: deterministic decoding.
JUDGE_TEMPERATURE = 0.0
JUDGE_MAX_TOKENS = 2048

# Reasoning models: no temperature knob. Thinking is disabled so the Judge is
# scoring rather than deliberating, and the token budget is higher because the
# reasoning envelope counts against it even at effort "none".
JUDGE_MAX_OUTPUT_TOKENS = 4096
JUDGE_REASONING_EFFORT = "none"


def uses_responses_endpoint(model: str) -> bool:
    return model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4"))


class JudgeRequestError(RuntimeError):
    pass


class JudgeClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        prompt_version: str,
        cache_path: Path,
        timeout: float = 360.0,
        max_attempts: int = 6,
    ) -> None:
        if not api_key:
            raise ValueError("JUDGE_API_KEY is required")
        from openai import OpenAI

        self.model = model
        self.prompt_version = prompt_version
        self.base_url = base_url
        self.timeout = timeout
        self.max_attempts = max_attempts
        self._use_responses = uses_responses_endpoint(model)
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._lock = threading.Lock()
        self._cache: dict[str, str] = {}
        self._cache_load_errors = 0
        self._load_cache()

    def _key(self, prompt: str) -> str:
        # The decoding parameters belong in the key, and the two endpoints do not
        # share a set: keying a /responses verdict on a temperature it never used
        # would let a cached chat verdict answer a reasoning-model request.
        if self._use_responses:
            params: dict[str, object] = {
                "endpoint": "responses",
                "max_output_tokens": JUDGE_MAX_OUTPUT_TOKENS,
                "reasoning_effort": JUDGE_REASONING_EFFORT,
            }
        else:
            params = {
                "endpoint": "chat.completions",
                "temperature": JUDGE_TEMPERATURE,
                "max_tokens": JUDGE_MAX_TOKENS,
            }
        payload = json.dumps(
            {
                "model": self.model,
                # The same model name is served by several gateways with
                # different prompts and decoding defaults, so the endpoint
                # belongs in the key: two base URLs are not the same Judge.
                "base_url": self.base_url,
                "prompt_version": self.prompt_version,
                "prompt": prompt,
                **params,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_cache(self) -> None:
        if not self.cache_path.is_file():
            return
        with self.cache_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    self._cache[record["key"]] = record["response"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    # An interrupted final append must not destroy earlier cache
                    # entries, so a malformed line is skipped -- line 1 included,
                    # but it is counted rather than dropped silently.
                    self._cache_load_errors += 1
                    continue

    def _cache_put(self, key: str, response: str) -> None:
        with self._lock:
            if key in self._cache:
                return
            self._cache[key] = response
            with self.cache_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"key": key, "response": response}, ensure_ascii=False))
                handle.write("\n")
                handle.flush()

    def _complete_via_chat(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=JUDGE_TEMPERATURE,
            max_tokens=JUDGE_MAX_TOKENS,
        )
        return response.choices[0].message.content or ""

    def _complete_via_responses(self, prompt: str) -> str:
        response = self._client.responses.create(
            model=self.model,
            input=prompt,
            max_output_tokens=JUDGE_MAX_OUTPUT_TOKENS,
            reasoning={"effort": JUDGE_REASONING_EFFORT},
        )
        # Walk the output blocks rather than reading output_text: with reasoning
        # enabled the array also carries reasoning items, and a provider that
        # ignores effort="none" would otherwise fold thinking into the verdict.
        parts = []
        for block in response.output or []:
            if getattr(block, "type", None) != "message":
                continue
            for item in getattr(block, "content", None) or []:
                if getattr(item, "type", None) == "output_text":
                    parts.append(getattr(item, "text", "") or "")
        return "".join(parts)

    def complete(
        self, prompt: str, validator: Callable[[str], bool] | None = None
    ) -> tuple[str, bool]:
        """Return (response_text, served_from_cache).

        ``validator`` gates the cache: a response it rejects -- an empty verdict,
        or one the caller cannot parse -- is retried and never written to the
        durable cache, so a single bad provider reply cannot answer later runs.
        """
        key = self._key(prompt)
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached, True

        error: BaseException | None = None
        for attempt in range(self.max_attempts):
            try:
                content = (
                    self._complete_via_responses(prompt) if self._use_responses
                    else self._complete_via_chat(prompt)
                )
                if validator is not None and not validator(content):
                    raise JudgeRequestError("judge response failed validation")
                self._cache_put(key, content)
                return content, False
            except BaseException as exc:
                error = exc
                status_code = getattr(exc, "status_code", None)
                retryable = status_code == 429 or (
                    isinstance(status_code, int) and 500 <= status_code < 600
                )
                # Connection/transport failures usually have no HTTP status.
                if status_code is None:
                    retryable = True
                if retryable and attempt + 1 < self.max_attempts:
                    time.sleep(min(2 ** (attempt + 1), 60) + random.uniform(0, 1))
                    continue
                break
        raise JudgeRequestError(
            f"Judge request failed after {self.max_attempts} attempts: {error}"
        ) from error

    @property
    def cache_entries(self) -> int:
        return len(self._cache)

    def clear_cache(self) -> None:
        """Drop the durable cache and delete its file.

        The escape hatch for a cache already poisoned by a bad provider reply:
        without it the only fix would be knowing the file path by heart.
        """
        with self._lock:
            self._cache.clear()
            if self.cache_path.is_file():
                self.cache_path.unlink()
