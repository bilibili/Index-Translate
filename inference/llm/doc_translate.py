#!/usr/bin/env python3
"""Translate long documents with Index-Nailong-2B / Index-Nailong-9B via any
OpenAI-compatible server (vLLM recommended).

Nailong is a long-context (262K) document-translation model. Unlike a generic
chat model it is served with FIXED per-direction prompt templates and a FIXED
greedy sampling profile — both are reproduced here exactly:

  * directions: zh-en / en-zh / zh-ja / ja-zh (templates in prompts/)
  * greedy: temperature=0, top_p=1, top_k=-1, min_p=0, seed=42
  * stop_token_ids=[248044, 248046], enable_thinking=False
  * no max_tokens by default: the server selects the output cap within its limits

Usage:
    python doc_translate.py novel.txt --direction zh-en -o novel.en.txt
    python doc_translate.py chapter.txt --source zh --target ja | less

Defaults assume:  vllm serve IndexTeam/Index-Nailong-9B --max-model-len 229376
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from openai import OpenAI


def make_client(base_url: str, api_key: str) -> OpenAI:
    """OpenAI client; bypass env/system proxies for local servers."""
    host = urlparse(base_url).hostname or ""
    if host in ("127.0.0.1", "localhost", "::1"):
        import httpx
        return OpenAI(base_url=base_url, api_key=api_key,
                      http_client=httpx.Client(trust_env=False))
    return OpenAI(base_url=base_url, api_key=api_key)

DEFAULT_MODEL = "IndexTeam/Index-Nailong-9B"
DIRECTIONS = ("zh-en", "en-zh", "zh-ja", "ja-zh", "en-ja", "ja-en")
# Marker inside each template, replaced by the full source text.
SRC_WORD = {"zh-en": "中文", "en-zh": "英文", "zh-ja": "中文", "ja-zh": "日文", "en-ja": "英文", "ja-en": "日文"}
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def load_template(direction: str) -> str:
    return (PROMPT_DIR / f"nailong_{direction}.txt").read_text(encoding="utf-8")


def render_prompt(direction: str, text: str) -> str:
    template = load_template(direction)
    marker = f"（在这里放入需要翻译的完整{SRC_WORD[direction]}原文）"
    assert template.count(marker) == 1, f"template {direction}: placeholder missing or duplicated"
    return template.replace(marker, text)


def resolve_direction(args) -> str:
    if args.direction:
        if args.direction not in DIRECTIONS:
            raise SystemExit(f"unknown direction {args.direction!r}, choose from {DIRECTIONS}")
        return args.direction
    pair = f"{args.source}-{args.target}"
    if pair in DIRECTIONS:
        return pair
    raise SystemExit(f"cannot derive direction from --source {args.source} --target {args.target}; "
                     f"pass --direction explicitly ({'/'.join(DIRECTIONS)})")


def main() -> None:
    ap = argparse.ArgumentParser(description="Long-document translation with Index-Nailong models")
    ap.add_argument("input", help="source text file (UTF-8), or - for stdin")
    ap.add_argument("-o", "--output", help="output file (default: stdout)")
    ap.add_argument("--direction", "-d", help="/".join(DIRECTIONS))
    ap.add_argument("--source", "-s", default="zh", help="source language code (used with --target if --direction omitted)")
    ap.add_argument("--target", "-t", default="en", help="target language code")
    ap.add_argument("--model", "-m", default=os.environ.get("INDEX_MODEL", DEFAULT_MODEL))
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8000/v1"))
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "EMPTY"))
    ap.add_argument("--max-tokens", type=int, default=0,
                    help="0 = omit max_tokens; the server selects the output cap within its limits")
    args = ap.parse_args()

    text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").strip()
    if not text:
        ap.error("empty input text")

    direction = resolve_direction(args)
    prompt = render_prompt(direction, text)

    kwargs = dict(
        model=args.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        top_p=1,
        seed=42,
        stream=True,
        extra_body={
            "top_k": -1,
            "min_p": 0,
            "presence_penalty": 0,
            "repetition_penalty": 1,
            "stop_token_ids": [248044, 248046],
            "ignore_eos": False,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    )
    if args.max_tokens > 0:
        kwargs["max_tokens"] = args.max_tokens

    client = make_client(args.base_url, args.api_key)
    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout
    try:
        with client.chat.completions.create(**kwargs) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    out.write(delta)
                    out.flush()
        out.write("\n")
    finally:
        if args.output:
            out.close()


if __name__ == "__main__":
    main()
