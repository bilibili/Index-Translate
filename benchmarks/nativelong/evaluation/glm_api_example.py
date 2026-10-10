#!/usr/bin/env python3
"""Obtain saved translations from the official GLM API for SEGALE evaluation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
ROOT = Path(__file__).resolve().parent


def read_rows(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def translate(row, key, settings, timeout):
    """Keep translation deltas only; an interrupted stream is not a valid output."""
    payload = {**settings, "messages": row["messages"]}
    record = {"case_id": row["case_id"], "status": "api_error", "mt": "",
              "model_id": settings["model"], "model_revision": None,
              "endpoint": ENDPOINT, "generation_config": settings,
              "generation_config_sha256": hashlib.sha256(
                  json.dumps(settings, sort_keys=True).encode()).hexdigest(),
              "finish_reason": None, "cap_hit": None,
              "input_tokens": None, "output_tokens": None}
    parts, done, usage = [], False, {}
    request = Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            for line in response:
                if not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    done = True
                    break
                if not data:
                    continue
                event = json.loads(data)
                if event.get("error"):
                    record["error"] = event["error"]
                    break
                if event.get("id"):
                    record["response_id"] = event["id"]
                if event.get("model"):
                    record["returned_model"] = event["model"]
                if event.get("usage"):
                    usage = event["usage"]
                for choice in event.get("choices", []):
                    if choice.get("index", 0) != 0:
                        continue
                    delta = choice.get("delta", {})
                    if delta.get("content"):
                        parts.append(delta["content"])
                    if delta.get("refusal"):
                        record["refusal"] = delta["refusal"]
                    if choice.get("finish_reason"):
                        record["finish_reason"] = choice["finish_reason"]
    except HTTPError as exc:
        with exc:
            record["http_status"] = exc.code
            record["error"] = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["mt"] = "".join(parts)
    record["stream_done"] = done
    record["usage"] = usage
    record["input_tokens"] = usage.get("prompt_tokens")
    record["output_tokens"] = usage.get("completion_tokens")
    finish = record["finish_reason"]
    if finish in ("sensitive", "content_filter") or error_code(record) == "1301":
        record["status"] = "content_filter"
    elif record.get("refusal"):
        record["status"] = "refused"
    elif done and finish in ("stop", "length") and record["mt"].strip() and "error" not in record:
        record["status"] = "ok"
        record["cap_hit"] = finish == "length"
    elif "error" not in record:
        record["error"] = "No complete, non-empty translation stream"
    # Never persist a credential echoed by an error response.
    record = json.loads(json.dumps(record, ensure_ascii=False).replace(key, "[REDACTED]"))
    record["output_sha256"] = hashlib.sha256(record["mt"].encode()).hexdigest()
    return record


def error_code(record: dict) -> str | None:
    """Return the provider error code from a structured body, never a substring match.

    Substring matching on the whole error text misclassified unrelated payloads
    (any token id, request id or echoed sequence containing "1301") as content
    filtering, so only explicit JSON code fields count here.
    """
    raw = record.get("error")
    if not isinstance(raw, str):
        return None
    try:
        body = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    nested = body.get("error") if isinstance(body.get("error"), dict) else {}
    for value in (body.get("code"), body.get("error_code"),
                  nested.get("code"), nested.get("type")):
        if isinstance(value, (str, int)):
            return str(value)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--example", action="store_true", help="Translate the two original short examples")
    selection.add_argument("--requests", type=Path, help="Dataset requests.jsonl; all rows unless --case-id is set")
    parser.add_argument("--case-id", help="Translate one selected case")
    parser.add_argument("--output", type=Path, required=True, help="New predictions JSONL file")
    parser.add_argument("--model", default="glm-5.3-flash")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Output ceiling, including thinking; raise for long cases")
    parser.add_argument("--timeout", type=float, default=1800, help="Socket timeout in seconds")
    args = parser.parse_args()
    key = os.environ.get("BIGMODEL_API_KEY", "").strip()
    if not key:
        parser.error("Set BIGMODEL_API_KEY in the environment")
    if args.max_tokens < 1 or args.timeout <= 0:
        parser.error("--max-tokens and --timeout must be positive")
    if args.output.exists():
        parser.error("--output must be a new file")
    if args.example:
        rows = [{"case_id": r["case_id"], "messages": [{"role": "user", "content":
                 "Translate the following Chinese text into English. Preserve all content and output only the translation.\n\n" + r["source"]}]}
                for r in read_rows(ROOT / "example/cases.jsonl")]
    else:
        rows = read_rows(args.requests)
    if args.case_id:
        rows = [r for r in rows if r["case_id"] == args.case_id]
    if not rows or len({r["case_id"] for r in rows}) != len(rows):
        parser.error("Select non-empty requests with unique case IDs")
    settings = {"model": args.model, "max_tokens": args.max_tokens,
                "temperature": 1, "top_p": 0.95, "reasoning_effort": "low",
                "thinking": {"type": "enabled", "clear_thinking": False},
                "stream": True, "stream_options": {"include_usage": True}, "tool_stream": True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        for row in rows:
            result = translate(row, key, settings, args.timeout)
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({k: result[k] for k in
                             ("case_id", "status", "finish_reason", "input_tokens", "output_tokens")}), flush=True)
            if result["status"] != "ok":
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
